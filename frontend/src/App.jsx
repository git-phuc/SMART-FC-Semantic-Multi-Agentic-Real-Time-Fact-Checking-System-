import { ArrowUp, Sparkles, Bot, User, XCircle } from "lucide-react";
import { useState, useEffect, useRef } from "react";

// Component thu gọn văn bản dài cho User
const ExpandableText = ({ text }) => {
  const [expanded, setExpanded] = useState(false);
  const maxLength = 300;
  
  if (!text || text.length <= maxLength) return <span className="break-words">{text}</span>;
  
  return (
    <div className="relative break-words">
      <span className={!expanded ? "opacity-90" : ""}>
        {expanded ? text : `${text.slice(0, maxLength)}...`}
      </span>
      <div className="mt-2 text-right">
        <button 
          onClick={() => setExpanded(!expanded)} 
          className="text-[11px] px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-foreground-subtle hover:text-white hover:bg-white/10 transition-colors uppercase font-mono tracking-wider active:scale-95"
        >
          {expanded ? "Thu gọn" : "Xem thêm"}
        </button>
      </div>
    </div>
  );
}

// Component mô phỏng hiệu ứng Typewriter (gõ chữ dần dần)
const TypewriterText = ({ text, speed = 8, onComplete }) => {
  const [displayed, setDisplayed] = useState("");
  const onCompleteRef = useRef(onComplete);
  
  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  useEffect(() => {
    setDisplayed("");
    if (!text) return;
    
    let i = 0;
    const interval = setInterval(() => {
      setDisplayed(text.slice(0, i));
      i++;
      if (i > text.length) {
        clearInterval(interval);
        if (onCompleteRef.current) onCompleteRef.current();
      }
    }, speed);
    return () => clearInterval(interval);
  }, [text, speed]);

  return <span>{displayed}</span>;
}

// Component hiển thị AI Response độc lập
const AIResponse = ({ data }) => {
  const [step, setStep] = useState(1); 
  // step 1: Hiện ngay Verdict + gõ Summary
  // step 2: Mở Arguments
  // step 2: Mở Arguments

  const verdict = data.verdict?.verdict || "CHƯA XÁC ĐỊNH";
  const confidence = data.verdict?.confidence_score || 0;
  
  const getVerdictStyle = (v) => {
    if (v === "THẬT") return "text-emerald-400 border-emerald-400/30 bg-[#050506]/95 shadow-[0_0_20px_rgba(52,211,153,0.15)]";
    if (v === "GIẢ") return "text-rose-400 border-rose-400/30 bg-[#050506]/95 shadow-[0_0_20px_rgba(251,113,133,0.15)]";
    return "text-amber-400 border-amber-400/30 bg-[#050506]/95 shadow-[0_0_20px_rgba(251,191,36,0.15)]";
  }

  const getVerdictLabel = (v) => {
    if (v === "THẬT") return "TIN THẬT";
    if (v === "GIẢ") return "TIN GIẢ";
    return "CHƯA XÁC THỰC";
  }

  return (
    <div className="flex flex-col gap-5 w-full h-fit max-w-3xl">
      
      {/* 1. Phần Phán Định (Verdict Box) - Tĩnh 100%, Độc lập với Text Width */}
      <div className={`shrink-0 w-full sm:w-[400px] mx-auto h-fit p-6 rounded-2xl border flex flex-col items-center justify-center text-center shadow-2xl ${getVerdictStyle(verdict)}`}>
        <div className="flex flex-col items-center gap-2">
          <Sparkles size={28} className="mb-1 opacity-80" />
          <h3 className="text-2xl md:text-3xl font-bold tracking-widest uppercase">
            {getVerdictLabel(verdict)}
          </h3>
        </div>
        
        <div className="px-4 py-1.5 mt-4 rounded-full bg-black/40 border border-white/10 text-[10px] md:text-xs font-mono tracking-widest">
          ĐỘ TIN CẬY: {(confidence * 100).toFixed(0)}%
        </div>
      </div>

      {/* 2. Phần Tóm tắt (Summary) với hiệu ứng gõ phím */}
      {step >= 1 && (
        <div className="p-6 rounded-2xl border border-border-default bg-[#0a0a0c] shadow-multi text-foreground-muted leading-relaxed text-[15px] animate-slide-up" style={{ animationDelay: '50ms' }}>
          <div className="flex items-center gap-2 mb-3 text-accent font-semibold text-[13px] uppercase tracking-wider">
            <Bot size={16} />
            <span>Đánh giá Tổng quan</span>
          </div>
          <TypewriterText 
            text={data.verdict?.summary || ""} 
            speed={15} 
            onComplete={() => setStep(2)} 
          />
          {step < 2 && <span className="inline-block w-1.5 h-4 ml-1 bg-accent animate-pulse align-middle" />}
        </div>
      )}

      {/* 3. Phần Luận Điểm (Arguments riêng biệt) */}
      {step >= 2 && data.verdict?.arguments && data.verdict.arguments.length > 0 && (
        <div className="space-y-4 animate-slide-up" style={{ animationFillMode: "both" }}>
          <div className="flex items-center gap-3 mb-2">
            <h4 className="text-xs font-mono tracking-widest text-foreground-subtle uppercase border border-border-default px-3 py-1 rounded-full bg-surface">
              Chi tiết Lập luận Kỹ thuật
            </h4>
            <div className="h-px bg-border-default flex-1"></div>
          </div>
          
          <div className="grid gap-4">
            {data.verdict.arguments.map((arg, idx) => (
               <div 
                 key={idx} 
                 className="p-5 rounded-xl bg-white/[0.02] border border-white/[0.04] shadow-multi hover:bg-white/[0.04] transition-colors group animate-slide-up"
                 style={{ animationDelay: `${idx * 400 + 100}ms`, animationFillMode: "both", opacity: 0 }}
               >
                <p className="font-semibold text-foreground mb-3 text-[15px] flex items-center gap-3">
                  <span className="w-6 h-6 rounded-full bg-accent/20 border border-accent/30 text-accent flex items-center justify-center text-xs font-mono">{idx+1}</span>
                  {arg.title}
                </p>
                <div className="text-foreground-muted text-[14.5px] leading-relaxed pl-9">
                  {arg.content}
                </div>
                {arg.source_url && (
                  <a href={arg.source_url} target="_blank" rel="noreferrer" className="block mt-4 pl-9 text-xs text-accent hover:text-accent-bright underline underline-offset-4 opacity-80 hover:opacity-100 transition-opacity">
                    🔗 Nguồn: {arg.source_name || "Trích dẫn Bài viết gốc"}
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function App() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState([]);
  
  const bottomRef = useRef(null);

  // Auto scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    
    const userMsg = { role: "user", content: query };
    setMessages(prev => [...prev, userMsg]);
    setQuery("");
    setLoading(true);
    
    try {
      const res = await fetch("http://localhost:8000/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: userMsg.content }) 
      });
      
      const data = await res.json();
      if (data.status === "error") throw new Error(data.message);
      
      setMessages(prev => [...prev, { role: "assistant", data: data.data }]);
    } catch (err) {
      setMessages(prev => [...prev, { role: "error", content: err.message || "Lỗi giao tiếp với Python Backend." }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen relative flex flex-col text-foreground selection:bg-accent/30 selection:text-white bg-[#050506]">
      
      {/* Background FX */}
      <div className="fixed inset-0 bg-[radial-gradient(ellipse_at_top,#0a0a0f_0%,#050506_50%,#020203_100%)] -z-20"></div>
      <div className="fixed top-[10%] left-[20%] w-[600px] h-[600px] bg-accent/15 blur-[120px] rounded-full -z-10 blob-primary opacity-50 pointer-events-none"></div>

      {/* Navbar Hóa trang */}
      <header className="fixed top-0 w-full h-14 border-b border-border-default bg-[#050506]/90 backdrop-blur-xl z-50 flex items-center justify-center shadow-multi">
        <div className="flex items-center gap-3 bg-surface border border-white/5 pl-2 pr-4 py-1 rounded-full">
          <div className="w-2.5 h-2.5 rounded-full bg-accent animate-pulse shadow-[0_0_12px_rgba(94,106,210,1)]"></div>
          <span className="text-xs font-mono tracking-widest text-foreground-subtle uppercase">SMART-FC Engine</span>
        </div>
      </header>

      {/* Vùng Lịch Sử Chat */}
      <div className="flex-1 overflow-y-auto pt-24 pb-48 px-4 sm:px-6">
        <div className="max-w-4xl mx-auto flex flex-col gap-10">
          
          {/* Default Landing / Empty State */}
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center text-center mt-20 opacity-90 animate-slide-up">
              <div className="w-20 h-20 rounded-3xl bg-surface border border-border-default flex items-center justify-center mb-8 shadow-multi">
                <Bot size={40} className="text-accent" />
              </div>
              <h2 className="text-4xl md:text-5xl font-semibold mb-5 tracking-tight bg-gradient-to-b from-white to-white/60 bg-clip-text text-transparent">
                Hệ thống sẵn sàng
              </h2>
              <p className="text-foreground-muted max-w-lg text-base md:text-lg leading-relaxed">
                Multi-Agent RAG đã trực tuyến. Gửi một tin đồn vào khung nhập liệu bên dưới để khơi nguồn chu trình truy xuất - phân tích - phán định.
              </p>
            </div>
          )}

          {/* Render Messages */}
          {messages.map((msg, idx) => (
            <div key={idx} className={`flex items-start gap-4 md:gap-6 ${msg.role === "user" ? "flex-row-reverse" : "flex-row"} animate-slide-up`}>
              
              {/* Avatar Robot / User */}
              <div className={`shrink-0 w-10 h-10 md:w-12 md:h-12 rounded-full flex items-center justify-center border shadow-multi ${msg.role === "user" ? "bg-white/5 border-white/10 text-foreground-subtle" : msg.role === "error" ? "bg-rose-500/10 border-rose-500/30 text-rose-400" : "bg-accent/10 border-accent/40 text-accent shadow-accent-glow"}`}>
                {msg.role === "user" ? <User size={20} /> : msg.role === "error" ? <XCircle size={20} /> : <Bot size={22} />}
              </div>

              {/* Chat Content */}
              <div className={`flex flex-col w-full max-w-[90%] md:max-w-[85%] ${msg.role === "user" ? "items-end w-auto" : "items-start"}`}>
                <span className="text-[11px] font-mono tracking-widest text-foreground-subtle mb-2 px-1 uppercase opacity-60">
                  {msg.role === "user" ? "Bạn" : msg.role === "error" ? "Lỗi Pipeline" : "SMART-FC Agent"}
                </span>
                
                {msg.role === "user" ? (
                  <div className="px-5 py-3.5 md:py-4 rounded-3xl rounded-tr-sm bg-white/[0.08] border border-white/5 text-foreground text-[15px] leading-relaxed shadow-multi">
                    <ExpandableText text={msg.content} />
                  </div>
                ) : msg.role === "error" ? (
                  <div className="px-5 py-3.5 rounded-3xl rounded-tl-sm bg-rose-500/10 border border-rose-500/20 text-rose-200 shadow-multi">
                    {msg.content}
                  </div>
                ) : (
                  <AIResponse data={msg.data} />
                )}
              </div>
            </div>
          ))}

          {/* Trạng thái Loading Sinh động */}
          {loading && (
            <div className="flex items-start gap-4 md:gap-6 animate-slide-up">
              <div className="shrink-0 w-10 h-10 md:w-12 md:h-12 rounded-full bg-accent/5 border border-accent/30 flex items-center justify-center text-accent shadow-accent-glow">
                <div className="w-5 h-5 border-[3px] border-accent/30 border-t-accent rounded-full animate-spin"></div>
              </div>
              <div className="flex flex-col">
                <span className="text-[11px] font-mono tracking-widest text-foreground-subtle mb-2 px-1 uppercase opacity-60">
                  Quá trình Suy luận Đa Tác tử
                </span>
                <div className="px-5 py-4 rounded-3xl rounded-tl-sm bg-surface border border-border-default flex gap-3 items-center shadow-multi">
                  <div className="flex gap-1.5">
                    <div className="w-2.5 h-2.5 rounded-full bg-accent animate-bounce" style={{ animationDelay: '0ms' }}></div>
                    <div className="w-2.5 h-2.5 rounded-full bg-accent animate-bounce" style={{ animationDelay: '150ms' }}></div>
                    <div className="w-2.5 h-2.5 rounded-full bg-accent animate-bounce" style={{ animationDelay: '300ms' }}></div>
                  </div>
                  <span className="ml-2 text-[13px] text-accent font-mono tracking-wide">Surfing the web & reasoning...</span>
                </div>
              </div>
            </div>
          )}
          
          <div ref={bottomRef} className="h-4" />
        </div>
      </div>

      {/* Khung Nhập Liệu (Input Box) Cố định Dưới Đáy */}
      <div className="fixed bottom-0 w-full bg-gradient-to-t from-[#020203] via-[#050506]/90 to-transparent pt-32 pb-8 px-4 z-40">
        <div className="max-w-3xl mx-auto">
          <form onSubmit={handleSearch} className="relative group">
            <div className="absolute inset-0 bg-accent-glow blur-2xl rounded-full opacity-0 group-focus-within:opacity-100 transition-opacity duration-700 -z-10"></div>
            <input 
              type="text" 
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              disabled={loading}
              placeholder="Gửi tin đồn cho hệ thống kiểm chứng..." 
              className="w-full h-16 rounded-2xl border border-white/10 bg-[#0a0a0c]/90 backdrop-blur-2xl shadow-multi pl-6 pr-16 text-foreground placeholder:text-foreground-subtle outline-none focus:ring-1 ring-accent/60 transition-all duration-300 text-[15px]"
            />
            <button 
              type="submit"
              disabled={loading || !query.trim()}
              className="absolute right-2 top-2 h-12 w-12 bg-[#5E6AD2] rounded-xl flex items-center justify-center text-white shadow-accent-glow transition-all duration-300 hover:bg-[#6872D9] active:scale-[0.96] disabled:opacity-30 disabled:hover:bg-[#5E6AD2] disabled:cursor-not-allowed"
            >
              <ArrowUp size={20} strokeWidth={2.5} />
            </button>
          </form>
          <div className="flex items-center justify-center gap-4 mt-4 opacity-50">
            <p className="text-[10px] font-mono text-foreground-subtle tracking-widest uppercase">
              Hai Lớp Ngữ Nghĩa
            </p>
            <span className="w-1 h-1 rounded-full bg-foreground-subtle"></span>
            <p className="text-[10px] font-mono text-foreground-subtle tracking-widest uppercase">
              Xác minh đa tác tử
            </p>
          </div>
        </div>
      </div>

    </div>
  );
}

export default App;
