"""
Two-Stage Semantic Cache với MongoDB Atlas Vector Search.

Kiến trúc 3 lớp:
  - Lớp 0 (Normalize): LLM chuẩn hóa câu hỏi → dạng cốt lõi (tránh miss do paraphrase)
  - Lớp 1 (Recall):    Vector Search tìm câu hỏi tương đồng (cosine > 0.80)
  - Lớp 2 (Precision):  NER + Regex so sánh thực thể (số, địa danh, tên người)

Cache HIT  → trả kết quả cũ trong < 3 giây
Cache MISS → chạy Multi-Agent pipeline → lưu kết quả mới vào DB
"""

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from dotenv import load_dotenv
from pathlib import Path
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]
from underthesea import ner  # type: ignore[import-untyped]

from utils.logger import get_logger, log_agent_step

# Load .env
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
logger = get_logger("Cache.Mongo")

# ============================================================
# Constants
# ============================================================
SIMILARITY_THRESHOLD = 0.88
CACHE_TTL_DAYS = 7
VECTOR_INDEX_NAME = "vector_index"
DB_NAME = "FakeNewsDB"
COLLECTION_NAME = "CacheLogs"


class MongoSemanticCache:
    """
    Two-Stage Semantic Cache cho hệ thống kiểm chứng tin tức.

    Stage 1: Embedding + Vector Search (MongoDB Atlas) → tìm candidate
    Stage 2: NER entity comparison → xác nhận chính xác

    Usage:
        cache = MongoSemanticCache()
        result = cache.check_cache("Bộ TC đề xuất thuế 5%...")
        if result["hit"]:
            print(result["data"])  # Trả kết quả cũ
        else:
            verdict = run_pipeline(...)
            cache.save_to_cache(query, verdict)
    """

    def __init__(self) -> None:
        """
        Khởi tạo kết nối MongoDB và load Embedding model.

        Raises:
            ValueError: Nếu MONGODB_URI chưa được cấu hình
        """
        # --- MongoDB ---
        mongo_uri = os.getenv("MONGODB_URI", "")
        if not mongo_uri:
            raise ValueError(
                "MONGODB_URI chưa được cấu hình.\n"
                "Mở file .env và thêm dòng:\n"
                "MONGODB_URI=mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/"
            )

        try:
            self.client: MongoClient = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            # Ping kiểm tra kết nối ngay
            self.client.admin.command("ping")
            self.db = self.client[DB_NAME]
            self.collection = self.db[COLLECTION_NAME]
            logger.info(f"[Cache] Connected to MongoDB Atlas — {DB_NAME}.{COLLECTION_NAME}")
        except PyMongoError as e:
            logger.error(f"[Cache] MongoDB connection failed: {e}")
            raise

        # --- Embedding Model ---
        # QUAN TRỌNG: Revert lại bản vietnamese-sbert theo yêu cầu của anh để khớp với DB cũ
        import gc
        logger.info("[Cache] Loading embedding model: keepitreal/vietnamese-sbert")
        self.embedder: SentenceTransformer = SentenceTransformer("keepitreal/vietnamese-sbert")
        gc.collect()  # Buộc Python dọn dẹp RAM dư thừa sau khi load model nặng
        logger.info("[Cache] Embedding model loaded successfully")

        # --- LLM cho Query Normalization (dùng Groq, siêu nhanh ~1s) ---
        from agents.query_agent import QueryAgent
        self.normalizer_agent = QueryAgent()
        logger.info("[Cache] Query normalizer Agent loaded (AGENT1/Groq)")

    # ============================================================
    # Stage 0: Query Normalization (LLM-based)
    # ============================================================
    _NORMALIZE_PROMPT = (
        "Trích xuất các sự kiện cốt lõi từ tin đồn sau thành 1 câu ngắn gọn duy nhất.\n"
        "BẮT BUỘC giữ lại nguyên vẹn TẤT CẢ các con số (số tiền, ngày tháng, phần trăm...).\n"
        "Giữ lại: chủ thể, hành động chính, thời gian, con số, địa danh, tên tổ chức.\n"
        "Bỏ hết: lời kêu gọi, cảm xúc, từ ngữ cường điệu, từ đệm.\n"
        "Viết thường, không dấu câu thừa, chỉ trả về đúng 1 câu.\n\n"
        'Tin đồn: "{query}"\n'
        "Câu chuẩn hóa:"
    )

    def _normalize_query(self, user_query: str) -> str:
        """
        Chuẩn hóa câu hỏi bằng LLM (Groq ~1s).
        Biến câu dài/cường điệu thành dạng cốt lõi ngắn gọn để embedding chính xác hơn.

        VD: "Cảnh báo khẩn cấp: Từ ngày 15/05/2026, tất cả thẻ BHYT bản giấy..."
          → "thẻ bhyt giấy hủy bỏ 15/05/2026 phí 150000 vssid tạm dừng quyền lợi"
        """
        try:
            prompt = self._NORMALIZE_PROMPT.format(query=user_query)
            normalized = self.normalizer_agent.call_llm(
                system_prompt="Bạn là chuyên gia ngôn ngữ học. Chỉ trả về một câu duy nhất.",
                user_prompt=prompt
            )
            normalized = normalized.strip().strip('"').strip()
            # Fallback nếu LLM trả về rỗng hoặc quá dài
            if not normalized or len(normalized) > len(user_query):
                logger.warning("[Cache] Normalize returned empty/too long, using raw query")
                return user_query
            log_agent_step(logger, "Cache", "Normalized query", f"{normalized[:100]}...")
            return normalized
        except Exception as e:
            logger.warning(f"[Cache] Normalize failed, using raw query: {e}")
            return user_query

    # ============================================================
    # Stage 2: Entity Extraction (NER + Regex)
    # ============================================================
    def _extract_entities(self, text: str) -> dict[str, set[str]]:
        """
        Bóc tách thực thể từ text bằng Regex (số) + Underthesea NER.

        Args:
            text: Văn bản cần trích xuất thực thể

        Returns:
            Dict chứa các set:
            {
                "nums": {"5", "50000000"},
                "loc":  {"việt nam"},
                "org":  {"bộ tài chính"},
                "per":  set()
            }
        """
        entities: dict[str, set[str]] = {
            "nums": set(),
            "loc": set(),
            "org": set(),
            "per": set(),
        }

        # --- Regex: trích xuất số có ≥ 2 chữ số (bỏ qua số 1 chữ số vì thường là noise) ---
        numbers = re.findall(r'\d{2,}', text)
        entities["nums"] = set(numbers)

        # --- Regex: trích xuất ngày tháng ---
        dates = re.findall(r'\d{1,2}/\d{1,4}(?:/\d{2,4})?', text)
        for d in dates:
            entities["nums"].add(d)

        # --- Underthesea NER ---
        try:
            ner_results = ner(text)
            # ner trả về list of tuples: [(word, pos, chunking, ner_tag), ...]
            current_entity = ""
            current_tag = ""

            for token in ner_results:
                word = token[0]
                tag = token[3]  # NER tag: B-PER, I-PER, B-LOC, I-LOC, B-ORG, I-ORG, O

                if tag.startswith("B-"):
                    # Lưu entity trước đó nếu có
                    if current_entity and current_tag:
                        self._add_entity(entities, current_tag, current_entity.strip())
                    # Bắt đầu entity mới
                    current_entity = word
                    current_tag = tag[2:]  # "PER", "LOC", "ORG"

                elif tag.startswith("I-") and tag[2:] == current_tag:
                    # Nối tiếp entity hiện tại
                    current_entity += " " + word

                else:
                    # Kết thúc entity
                    if current_entity and current_tag:
                        self._add_entity(entities, current_tag, current_entity.strip())
                    current_entity = ""
                    current_tag = ""

            # Xử lý entity cuối cùng
            if current_entity and current_tag:
                self._add_entity(entities, current_tag, current_entity.strip())

        except Exception as e:
            logger.warning(f"[Cache] NER extraction error: {e}")

        return entities

    @staticmethod
    def _add_entity(entities: dict[str, set[str]], tag: str, value: str) -> None:
        """Thêm entity vào đúng category."""
        tag_map = {"PER": "per", "LOC": "loc", "ORG": "org"}
        key = tag_map.get(tag)
        if key:
            entities[key].add(value.lower())

    # ============================================================
    # Stage 1: Vector Search (MongoDB Atlas)
    # ============================================================
    def check_cache(self, user_query: str) -> dict[str, Any]:
        """
        Kiểm tra cache 2 lớp.

        Lớp 1: Vector Search tìm candidate (cosine > SIMILARITY_THRESHOLD)
        Lớp 2: So sánh entities (nums + loc phải khớp 100%)

        Args:
            user_query: Câu hỏi/tin đồn từ user

        Returns:
            {"hit": True, "data": {...verdict...}} nếu cache hit
            {"hit": False} nếu cache miss
        """
        try:
            log_agent_step(logger, "Cache", "Checking cache", f"Query: {user_query[:80]}...")

            # --- Lớp 0: Normalize query bằng LLM ---
            normalized = self._normalize_query(user_query)

            # --- Lớp 1: Embedding + Vector Search (dùng câu đã normalize) ---
            query_vector = self.embedder.encode(normalized).tolist()

            pipeline = [
                {
                    "$vectorSearch": {
                        "index": VECTOR_INDEX_NAME,
                        "path": "vector",
                        "queryVector": query_vector,
                        "numCandidates": 10,
                        "limit": 3,  # Top 3 candidates
                    }
                },
                {
                    "$addFields": {
                        "score": {"$meta": "vectorSearchScore"}
                    }
                },
                {
                    # Lọc bỏ documents đã hết hạn
                    "$match": {
                        "expires_at": {"$gte": datetime.now(timezone.utc)}
                    }
                },
            ]

            candidates = list(self.collection.aggregate(pipeline))

            if not candidates:
                log_agent_step(logger, "Cache", "Cache MISS", "Không tìm thấy candidate nào")
                return {"hit": False}

            # --- Lớp 2: NER Comparison cho từng candidate ---
            new_ent_raw = self._extract_entities(user_query)
            new_ent_norm = self._extract_entities(normalized)
            new_entities = {k: new_ent_raw.get(k, set()) | new_ent_norm.get(k, set()) for k in new_ent_raw}
            log_agent_step(
                logger, "Cache", "Extracted entities (query)",
                f"nums={new_entities['nums']}, loc={new_entities['loc']}, "
                f"org={new_entities['org']}, per={new_entities['per']}"
            )

            for candidate in candidates:
                score = candidate.get("score", 0.0)

                if score < SIMILARITY_THRESHOLD:
                    log_agent_step(
                        logger, "Cache", "Score too low",
                        f"score={score:.4f} < {SIMILARITY_THRESHOLD}"
                    )
                    continue

                # Lấy entities đã lưu trong cache
                cached_entities_raw = candidate.get("entities", {})
                cached_entities: dict[str, set[str]] = {
                    k: set(v) for k, v in cached_entities_raw.items()
                }

                log_agent_step(
                    logger, "Cache", "Comparing entities",
                    f"score={score:.4f} | "
                    f"cached_nums={cached_entities.get('nums', set[str]())}, "
                    f"cached_loc={cached_entities.get('loc', set[str]())}"
                )

                nums_match = (
                    not new_entities["nums"]  # query mới không có số → skip
                    or new_entities["nums"].issubset(cached_entities.get("nums", set()))
                )

                # Check chống false positive tên người (vd: Tô Lâm vs Volodin)
                # Nếu query mới có tên người, phải ĐẢM BẢO toàn bộ các tên người đều xuất hiện trong cache
                # Tránh tình trạng: Query = "Tô Lâm và Putin" map nhầm vào cache "Tô Lâm" đơn thuần
                person_match = True
                if new_entities["per"]:
                    cached_per = cached_entities.get("per", set())
                    for np in new_entities["per"]:
                        # Tìm xem tên np có khớp một phần với cp nào trong cached không
                        match_found_for_this_person = False
                        for cp in cached_per:
                            if np in cp or cp in np:
                                match_found_for_this_person = True
                                break
                        
                        if not match_found_for_this_person:
                            person_match = False
                            break

                if nums_match and person_match:
                    # Cache HIT!
                    log_agent_step(
                        logger, "Cache", "Cache HIT ✅",
                        f"score={score:.4f} | Entities khớp an toàn"
                    )

                    # Tăng hit_count
                    self.collection.update_one(
                        {"_id": candidate["_id"]},
                        {"$inc": {"hit_count": 1}}
                    )

                    return {
                        "hit": True,
                        "data": candidate.get("full_response", {}),
                        "score": score,
                        "cached_query": candidate.get("query", ""),
                    }

                log_agent_step(
                    logger, "Cache", "Entities LỆCH ❌",
                    f"nums_match={nums_match}"
                )

            # Không candidate nào pass Lớp 2
            log_agent_step(logger, "Cache", "Cache MISS", "Có candidate nhưng entities không khớp")
            return {"hit": False}

        except PyMongoError as e:
            logger.error(f"[Cache] MongoDB error during check: {e}")
            return {"hit": False}
        except Exception as e:
            logger.error(f"[Cache] Unexpected error during check: {e}")
            return {"hit": False}

    # ============================================================
    # Save to Cache
    # ============================================================
    def save_to_cache(self, user_query: str, full_response: dict) -> bool:
        """
        Lưu kết quả kiểm chứng vào MongoDB để phục vụ cache tương lai.

        Args:
            user_query: Câu hỏi gốc từ user
            full_response: Toàn bộ verdict dict từ Agent 3

        Returns:
            True nếu lưu thành công, False nếu lỗi
        """
        try:
            log_agent_step(logger, "Cache", "Saving to cache", f"Query: {user_query[:80]}...")

            # Normalize query trước khi encode (đảm bảo cùng dạng với check_cache)
            normalized = self._normalize_query(user_query)

            # Encode vector từ câu đã normalize
            query_vector = self.embedder.encode(normalized).tolist()

            # Trích xuất entities (kết hợp cả raw query & normalized để không lọt số)
            ent_raw = self._extract_entities(user_query)
            ent_norm = self._extract_entities(normalized)
            entities = {k: ent_raw.get(k, set()) | ent_norm.get(k, set()) for k in ent_raw}
            # Convert sets → lists cho BSON serialization
            entities_serializable = {k: list(v) for k, v in entities.items()}

            now = datetime.now(timezone.utc)

            document = {
                "query": user_query,
                "vector": query_vector,
                "entities": entities_serializable,
                "full_response": full_response,
                "created_at": now,
                "expires_at": now + timedelta(days=CACHE_TTL_DAYS),
                "hit_count": 0,
            }

            self.collection.insert_one(document)

            log_agent_step(
                logger, "Cache", "Saved ✅",
                f"entities: nums={entities['nums']}, loc={entities['loc']}"
            )
            return True

        except PyMongoError as e:
            logger.error(f"[Cache] MongoDB save error: {e}")
            return False
        except Exception as e:
            logger.error(f"[Cache] Unexpected save error: {e}")
            return False

    # ============================================================
    # Utility
    # ============================================================
    def get_stats(self) -> dict:
        """Trả về thống kê cache."""
        try:
            total = self.collection.count_documents({})
            active = self.collection.count_documents(
                {"expires_at": {"$gte": datetime.now(timezone.utc)}}
            )
            total_hits = sum(
                doc.get("hit_count", 0)
                for doc in self.collection.find({}, {"hit_count": 1})
            )
            return {
                "total_documents": total,
                "active_documents": active,
                "expired_documents": total - active,
                "total_cache_hits": total_hits,
            }
        except Exception:
            return {"error": "Cannot retrieve stats"}


# ============================================================
# Singleton helper — dùng chung 1 instance trong toàn app
# ============================================================
_cache_instance: MongoSemanticCache | None = None


def get_cache() -> MongoSemanticCache | None:
    """
    Trả về singleton MongoSemanticCache.
    Nếu chưa khởi tạo thì tạo mới, lưu lại để tái sử dụng.
    Trả về None nếu MONGODB_URI chưa cấu hình hoặc kết nối lỗi.
    """
    global _cache_instance
    if _cache_instance is None:
        try:
            _cache_instance = MongoSemanticCache()
        except Exception as e:
            logger.warning(f"[Cache] Khởi tạo cache thất bại, fallback no-cache: {e}")
            return None
    return _cache_instance
