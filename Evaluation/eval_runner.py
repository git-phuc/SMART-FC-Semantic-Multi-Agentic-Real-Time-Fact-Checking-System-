"""
Evaluation Runner
=================
Đưa các câu hỏi từ eval-questions-generated.csv vào pipeline SMART-FC,
sau đó ghi kết quả (Decision, output_1-3, link_1-3, label_model) vào CSV.

Hỗ trợ:
  - Resume: skip các row đã có kết quả (Decision != rỗng)
  - Rate limit: delay giữa các request
  - Error handling: ghi lỗi vào CSV, không crash toàn bộ
"""

import csv
import os
import sys
import time
import json
import traceback

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.theme import Theme
    from rich.text import Text
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
except ImportError:
    os.system("pip install rich")
    from rich.console import Console
    from rich.panel import Panel
    from rich.theme import Theme
    from rich.text import Text
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn

# Thêm backend vào path để import pipeline
BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
sys.path.insert(0, BACKEND_DIR)

# Load .env từ backend
from dotenv import load_dotenv
load_dotenv(os.path.join(BACKEND_DIR, ".env"))

from graph.workflow import run_verification  # Chạy TRỰC TIẾP, KHÔNG qua cache/DB
from utils.logger import get_logger

logger = get_logger("Evaluation.Runner")

# Định dạng theme cho CLI
custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "question": "bold magenta",
    "dim": "dim white",
})
console = Console(theme=custom_theme)

# ──────────── CẤU HÌNH ────────────
INPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Data", "Posetive", "posetive-news-evaluation-v2.csv")
if len(sys.argv) > 1:
    INPUT_FILE = sys.argv[1]
OUTPUT_FILE = INPUT_FILE  # Ghi đè trực tiếp
TEMP_FILE = INPUT_FILE.replace(".csv", ".tmp.csv")

DELAY_BETWEEN_REQUESTS = 3  # Giây delay giữa mỗi request
BATCH_SIZE = 6              # Chạy mấy bài thì ngừng
SLEEP_AFTER_BATCH = 90      # Giây ngừng (1.5 phút chống ban)

# ──────────── PARSE VERDICT ────────────
def parse_verdict(state: dict) -> dict:
    verdict = state.get("verdict", {})
    decision = verdict.get("summary", verdict.get("explanation", ""))
    
    label_model = verdict.get("verdict", "CHƯA XÁC ĐỊNH")
    arguments = verdict.get("arguments", [])
    
    outputs = {}
    for i in range(3):
        if i < len(arguments):
            arg = arguments[i]
            content = arg.get("content", "")
            evidence = arg.get("evidence", "")
            # Ghép content + evidence cho đầy đủ luận chứng
            if evidence and evidence.strip() and evidence.strip() != content.strip():
                output_text = f"{content}\n[Bằng chứng]: {evidence}"
            else:
                output_text = content
            source_url = arg.get("source_url", "")
            outputs[f"output_{i+1}"] = output_text
            outputs[f"link_{i+1}"] = source_url
        else:
            outputs[f"output_{i+1}"] = ""
            outputs[f"link_{i+1}"] = ""
    
    return {
        "Decision": decision,
        **outputs,
        "label_model": label_model,
    }


# ──────────── MAIN ────────────
def main():
    console.clear()
    console.print(Panel.fit("[bold cyan]SMART-FC EVALUATION RUNNER[/]\n[dim]Direct Pipeline Execution & Benchmarking[/]", border_style="cyan"))

    if not os.path.exists(INPUT_FILE):
        console.print(f"[error]❌ Không tìm thấy file: {INPUT_FILE}[/]")
        return

    with open(INPUT_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        all_rows = list(reader)

    console.print(f"📂 Đọc được [bold white]{len(all_rows)}[/] câu hỏi từ [info]{os.path.basename(INPUT_FILE)}[/]")
    
    required_fields = ["Decision", "output_1", "link_1", "output_2", "link_2", "output_3", "link_3", "label_model"]
    for field in required_fields:
        if field not in fieldnames:
            fieldnames.append(field)

    rows_to_process = []
    for i, row in enumerate(all_rows):
        decision = (row.get("Decision") or "").strip()
        question = (row.get("question") or "").strip()
        
        if not decision and question:
            rows_to_process.append(i)
        elif not question:
            logger.warning(f"⏩ Line {i+2}: Bỏ qua vì không tìm thấy câu hỏi.")
    
    completed = len(all_rows) - len(rows_to_process)
    console.print(f"✅ Đã có kết quả: [success]{completed}[/] bài")
    console.print(f"🚀 Cần xử lý: [warning]{len(rows_to_process)}[/] bài")
    console.print(f"⏱️  Anti-spam: Lặp [bold white]{BATCH_SIZE}[/] bài sẽ nghỉ [bold white]{SLEEP_AFTER_BATCH}s[/]\n")

    if not rows_to_process:
        console.print(Panel("[bold green]✅ Tất cả đã được xử lý xong hoặc không có câu hỏi hợp lệ![/] 🎉", border_style="green"))
        return

    success = 0
    failed = 0

    for count, row_idx in enumerate(rows_to_process, 1):
        row = all_rows[row_idx]
        idx = row.get("index", "?")
        title = row.get("title", "")
        question = row.get("question", "")

        q_panel = Panel(
            f"[dim]Question:[/]\n[white]{question}[/]", 
            title=f"[bold magenta]🔄 ĐANG GIẢI QUYẾT [{count}/{len(rows_to_process)}] - INDEX: {idx}[/]", 
            subtitle=f"[dim]{title[:80]}...[/]",
            border_style="magenta"
        )
        console.print(q_panel)

        try:
            start_time = time.time()
            
            # Using rich status spinner for the model inference
            with console.status("[bold cyan]🔄 Đang phân tích qua Multi-Agent Pipeline rà soát sự thật...[/]", spinner="dots"):
                final_state = run_verification(question)
                
            elapsed = time.time() - start_time
            result = parse_verdict(final_state)
            
            for key, value in result.items():
                all_rows[row_idx][key] = value

            with open(TEMP_FILE, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_rows)
            
            for r in range(3):
                try:
                    os.replace(TEMP_FILE, OUTPUT_FILE)
                    break
                except PermissionError:
                    if r < 2:
                        console.print(f"  [warning]⚠️ CẢNH BÁO: Excel đang mở file? Đóng ngay file để tránh lỗi. Thử lại sau 3s... (Lần {r+1}/3)[/]")
                        time.sleep(3)
                    else:
                        raise PermissionError("KHÔNG THỂ GHI FILE CSV. HÃY ĐÓNG EXCEL VÀ CHẠY LẠI SCRIPT!")

            label = result.get("label_model", "ERROR")
            if "THẬT" in label.upper() and "GIẢ" not in label.upper():
                label_color = "bold green"
            elif "GIẢ" in label.upper():
                label_color = "bold red"
            else:
                label_color = "bold yellow"

            cot_display = ""
            cot_text = final_state.get("verdict", {}).get("chain_of_thought", "").strip()
            if cot_text:
                cot_display = f"[dim italic]🧠 CoT:[/] [italic magenta]{cot_text}[/]\n"

            res_panel = Panel(
                f"[dim]Verdict:[/] [{label_color}]{label}[/]\n{cot_display}[dim]Reasoning:[/] {result['Decision']}\n[dim]Time:[/] {elapsed:.1f}s",
                border_style="green"
            )
            console.print(res_panel)
            success += 1

        except Exception as e:
            elapsed = time.time() - start_time
            error_msg = str(e)[:200]
            console.print(Panel(f"[bold red]❌ LỖI SAU {elapsed:.1f}s:[/]\n{error_msg}", border_style="red"))
            logger.error(f"[Runner] Error index={idx}: {traceback.format_exc()}")
            
            all_rows[row_idx]["Decision"] = f"[ERROR] {error_msg[:150]}"
            all_rows[row_idx]["label_model"] = "ERROR"
            
            with open(TEMP_FILE, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_rows)
            os.replace(TEMP_FILE, OUTPUT_FILE)
            failed += 1

        print("")

        if count < len(rows_to_process):
            if count % BATCH_SIZE == 0:
                with console.status(f"[bold yellow]🛑 Đã chạy {BATCH_SIZE} bài. Hệ thống nghỉ làm mát {SLEEP_AFTER_BATCH}s (Chống API Limit)...[/]", spinner="moon"):
                    time.sleep(SLEEP_AFTER_BATCH)
            else:
                with console.status(f"[dim]💤 Chờ {DELAY_BETWEEN_REQUESTS}s nhịp request...[/]", spinner="point"):
                    time.sleep(DELAY_BETWEEN_REQUESTS)

    # Tổng kết
    summary = f"""[bold white]TỔNG KẾT ĐÁNH GIÁ[/]
[success]✅ Thành công:[/] {success}
[error]❌ Thất bại:[/]  {failed}
[info]📄 Output:[/]    {OUTPUT_FILE}
"""
    console.print(Panel(summary, title="[bold cyan]HOÀN THÀNH[/]", border_style="cyan"))

if __name__ == "__main__":
    main()
