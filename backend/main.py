"""
Main entry point - CLI interface cho hệ thống kiểm chứng tin tức.
Hỗ trợ chế độ: single query hoặc interactive mode.
"""

import argparse
import json
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich import box

from graph.workflow import run_verification_with_cache as run_verification

console = Console()


def display_verdict(state: dict) -> None:
    """
    Hiển thị kết quả kiểm chứng với format đẹp (rich).

    Args:
        state: Final state dictionary từ pipeline
    """
    verdict = state.get("verdict", {})
    user_input = state.get("user_input", "")

    # === Header ===
    console.print()
    console.print(Panel(
        f"[bold]{user_input}[/bold]",
        title="📰 Thông tin cần kiểm chứng",
        border_style="blue",
    ))

    # === Verdict ===
    verdict_text = verdict.get("verdict", "CHƯA XÁC ĐỊNH")
    verdict_en = verdict.get("verdict_en", "UNVERIFIED")
    confidence = verdict.get("confidence_score", 0.0)

    # Chọn màu dựa trên verdict
    color_map = {
        "THẬT": "green",
        "GIẢ": "red",
        "CHƯA XÁC ĐỊNH": "yellow",
        "MỘT PHẦN ĐÚNG": "orange3",
    }
    color = color_map.get(verdict_text, "white")

    # Confidence bar
    filled = int(confidence * 20)
    bar = "█" * filled + "░" * (20 - filled)

    console.print(Panel(
        f"[bold {color}]{verdict_text} ({verdict_en})[/bold {color}]\n\n"
        f"Độ tin cậy: [{color}]{bar}[/{color}] {confidence:.0%}",
        title="🔍 Phán định",
        border_style=color,
    ))

    # === Tóm tắt kết luận ===
    summary = verdict.get("summary", verdict.get("explanation", "Không có giải thích."))
    console.print(Panel(
        f"[bold]{summary}[/bold]",
        title="💡 Kết luận",
        border_style="cyan",
    ))

    # === Luận điểm chứng minh ===
    arguments = verdict.get("arguments", [])
    if arguments:
        console.print()
        console.rule("[bold yellow]📝 Luận điểm & Bằng chứng[/bold yellow]")
        for i, arg in enumerate(arguments, 1):
            title = arg.get("title", f"Luận điểm {i}")
            content = arg.get("content", "")
            evidence = arg.get("evidence", "")
            src_name = arg.get("source_name", "")
            src_url = arg.get("source_url", "")

            detail = content
            if evidence:
                detail += f"\n\n[italic]� Dẫn chứng: {evidence}[/italic]"
            if src_name or src_url:
                detail += f"\n[blue]🔗 {src_name}: {src_url}[/blue]"

            console.print(Panel(
                detail,
                title=f"[bold]{i}. {title}[/bold]",
                border_style="yellow",
                padding=(0, 1),
            ))

    # === Phân tích chi tiết ===
    reasoning = verdict.get("reasoning", {})
    if reasoning:
        table = Table(title="📋 Phân tích chi tiết", box=box.ROUNDED, show_lines=True)
        table.add_column("Hạng mục", style="bold", width=25)
        table.add_column("Chi tiết", min_width=50)

        table.add_row(
            "Đánh giá bằng chứng",
            reasoning.get("evidence_assessment", "N/A"),
        )

        supporting = reasoning.get("supporting_evidence", [])
        if supporting:
            table.add_row(
                "✅ Bằng chứng ủng hộ",
                "\n".join(f"• {e}" for e in supporting),
            )

        contradicting = reasoning.get("contradicting_evidence", [])
        if contradicting:
            table.add_row(
                "❌ Bằng chứng phản bác",
                "\n".join(f"• {e}" for e in contradicting),
            )

        table.add_row(
            "Phân tích logic",
            reasoning.get("logical_analysis", "N/A"),
        )
        console.print(table)


    # === Khuyến nghị ===
    recommendation = verdict.get("recommendation", "")
    if recommendation:
        console.print(Panel(
            recommendation,
            title="📌 Khuyến nghị",
            border_style="magenta",
        ))

    # === Pipeline logs ===
    console.print()
    logs = state.get("agent_logs", [])
    if logs:
        log_text = "\n".join(f"  {log}" for log in logs)
        console.print(Panel(
            log_text,
            title="📝 Pipeline Logs",
            border_style="dim",
        ))



def interactive_mode():
    """Chế độ tương tác - nhập nhiều tin liên tục."""
    console.print(Panel(
        "[bold cyan]Multi-Agent Vietnamese Fake News Verification System[/bold cyan]\n"
        "Nhập tin tức cần kiểm chứng. Gõ 'quit' hoặc 'exit' để thoát.",
        title="🤖 Hệ thống kiểm chứng tin tức",
        border_style="cyan",
    ))

    while True:
        console.print()
        claim = console.input("[bold green]📰 Nhập tin cần kiểm chứng:[/bold green] ").strip()

        if claim.lower() in ("quit", "exit", "q"):
            console.print("[yellow]👋 Tạm biệt![/yellow]")
            break

        if not claim:
            console.print("[red]⚠️ Vui lòng nhập nội dung tin tức.[/red]")
            continue

        console.print()
        with console.status("[bold cyan]🔄 Đang kiểm chứng...[/bold cyan]", spinner="dots"):
            try:
                final_state = run_verification(claim)
                display_verdict(final_state)
            except Exception as e:
                console.print(f"[red]❌ Lỗi: {e}[/red]")
                console.print("[yellow]Hãy kiểm tra API keys trong file .env[/yellow]")


def single_query_mode(claim: str, output_json: bool = False):
    """
    Chế độ chạy một lần với query từ command line.

    Args:
        claim: Tin cần kiểm chứng
        output_json: Nếu True, xuất kết quả dưới dạng JSON (cho scripting)
    """
    if output_json:
        # Mode JSON output (cho scripting/API integration)
        try:
            final_state = run_verification(claim)
            print(json.dumps(final_state.get("verdict", {}), ensure_ascii=False, indent=2))
        except Exception as e:
            print(json.dumps({"error": str(e)}, ensure_ascii=False))
            sys.exit(1)
    else:
        # Mode hiển thị đẹp
        with console.status("[bold cyan]🔄 Đang kiểm chứng...[/bold cyan]", spinner="dots"):
            try:
                final_state = run_verification(claim)
            except Exception as e:
                console.print(f"[red]❌ Lỗi: {e}[/red]")
                console.print("[yellow]Hãy kiểm tra API keys trong file .env[/yellow]")
                sys.exit(1)

        display_verdict(final_state)


def main():
    """Entry point chính."""
    parser = argparse.ArgumentParser(
        description="🤖 Multi-Agent Vietnamese Fake News Verification System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ sử dụng:
  python main.py --interactive
  python main.py --query "Việt Nam vô địch AFF Cup 2024"
  python main.py --query "NASA tuyên bố Trái Đất phẳng" --json
        """,
    )

    parser.add_argument(
        "--query", "-q",
        type=str,
        help="Tin tức cần kiểm chứng (mode chạy một lần)",
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Chế độ tương tác (nhập nhiều tin liên tục)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Xuất kết quả dưới dạng JSON (dùng cho scripting)",
    )

    args = parser.parse_args()

    if args.interactive:
        interactive_mode()
    elif args.query:
        single_query_mode(args.query, output_json=args.json)
    else:
        # Mặc định chạy interactive
        interactive_mode()


if __name__ == "__main__":
    main()
