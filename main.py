"""
NextDNS Auto-Register Tool
Automatically registers NextDNS accounts and extracts API keys
using temporary emails from tinyhost.shop + Playwright browser automation.

Made by: henxi

Usage:
  python main.py                  # Ask how many to generate
  python main.py --count 10       # Generate 10 directly
  python main.py -c 10 -o keys.txt --visible  # Visible browser mode
"""
import sys
import io

# Fix Windows console Unicode support
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True
    )

import warnings
import threading
# Suppress asyncio cleanup warnings on Windows (benign, happen after browser closes)
warnings.filterwarnings("ignore", category=ResourceWarning)
# Suppress asyncio unraisable hook warnings (Playwright subprocess cleanup)
def _suppress_unraisable(unraisable):
    msg = str(unraisable.exc_value) if unraisable.exc_value else ""
    if any(x in msg for x in ["I/O operation on closed pipe", "unclosed transport"]):
        return
    sys.__unraisablehook__(unraisable)

sys.unraisablehook = _suppress_unraisable

import time
import argparse
import asyncio
import traceback
from datetime import datetime
from typing import Optional
import os
import requests

from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
)
from rich.panel import Panel
from rich.table import Table

import config
from tinyhost import TinyhostClient
from nextdns import NextDNSEngine, NextDNSResult
from logger import log
from config import OUTPUT_FILE


console = Console(safe_box=True, legacy_windows=False)

# Configuration
DENYLIST_DOMAINS = ["api.revenuecat.com"]


def add_to_denylist(api_key: str, profile_id: str, domains: list[str]):
    """
    Add domains to NextDNS denylist automatically.
    """
    for domain in domains:
        try:
            headers = {
                'X-Api-Key': api_key,
                'Content-Type': 'application/json'
            }
            
            url = f'https://api.nextdns.io/profiles/{profile_id}/denylist'
            payload = {'id': domain}
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            if response.status_code in [200, 201, 204]:
                log.info(f"  [Denylist] Added '{domain}' ✓")
            else:
                log.warning(f"  [Denylist] Failed to add '{domain}': {response.status_code}")
        except Exception as e:
            log.warning(f"  [Denylist] Error adding '{domain}': {e}")


def save_result(result: NextDNSResult):
    """Save successful registration result to output file."""
    if not result.success:
        return
    timestamp = result.created_at or ""
    
    # Generate profile link
    profile_link = f"https://apple.nextdns.io/?profile={result.profile_id}" if result.profile_id else "N/A"
    
    # Save to api_keys.txt with profile link
    line = f"{result.email}|{result.password}|{result.api_key}|{result.profile_id or 'N/A'}|{profile_link}|{timestamp}"
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    log.info(f"  [File] Saved to {OUTPUT_FILE}")
    
    # Save to profile_links.txt for easy access
    profile_links_file = "profile_links.txt"
    link_line = f"{profile_link}|{result.api_key}"
    with open(profile_links_file, "a", encoding="utf-8") as f:
        f.write(link_line + "\n")
    log.info(f"  [Profile Link] Saved to {profile_links_file}")
    
    # Automatically add to denylist if we have API key and profile ID
    if result.api_key and result.profile_id:
        add_to_denylist(result.api_key, result.profile_id, DENYLIST_DOMAINS)


async def register_single(
    tinyhost: TinyhostClient,
    visible: bool = False,
    password: Optional[str] = None,
) -> Optional[NextDNSResult]:
    """
    Complete flow for one account:
    1. Generate temp email from tinyhost
    2. Register NextDNS via Playwright
    3. Return result
    """
    # Step 1: Generate temp email
    email, domain, user = tinyhost.generate_email()

    # Generate password
    if password:
        pwd = password
    else:
        import random
        import string
        charset = string.ascii_letters + string.digits
        pwd = ''.join(random.choices(charset, k=14))

    log.info(f"  [NextDNS] Registering: {email}")

    # Step 2: Register via Playwright
    try:
        engine = NextDNSEngine(
            email=email,
            password=pwd,
            headless=not visible,
        )
        result = await engine.register()
        if result.success and result.api_key and result.api_key != "NOT_FOUND":
            save_result(result)
        return result
    except Exception as e:
        log.error(f"  [NextDNS] Unexpected error: {e}")
        log.debug(traceback.format_exc())
        return None


async def run_batch(count: int, output_file: str, visible: bool, password: Optional[str]):
    """Run batch registration with progress display."""
    global OUTPUT_FILE
    OUTPUT_FILE = output_file

    # Create output file if not exists (don't clear existing results)
    if not os.path.exists(OUTPUT_FILE):
        open(OUTPUT_FILE, "w", encoding="utf-8").close()

    console.print(Panel.fit(
        f"[bold cyan]NextDNS Auto-Register Tool[/bold cyan]  |  "
        f"[yellow]{count}[/yellow] accounts via tinyhost.shop + Playwright\n"
        f"[dim]Made by henxi[/dim]",
        border_style="cyan",
    ))

    results: list[NextDNSResult] = []
    failures = 0
    not_found = 0

    # Reuse a single tinyhost client for all registrations
    tinyhost = TinyhostClient()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=False,
    ) as progress:

        main_task = progress.add_task("[cyan]Starting...", total=count)

        for i in range(count):
            progress.update(
                main_task,
                description=(
                    f"[cyan]Account {i + 1}/{count} — "
                    f"[green]ok: {len(results)}[/green] / "
                    f"[yellow]not_found: {not_found}[/yellow] / "
                    f"[red]failed: {failures}[/red]"
                ),
            )

            result = await register_single(tinyhost, visible, password)

            if result:
                if result.success:
                    if result.api_key == "NOT_FOUND":
                        not_found += 1
                    else:
                        results.append(result)
                else:
                    failures += 1
            else:
                failures += 1

            # Delay between registrations to avoid rate limiting
            if i < count - 1:
                await asyncio.sleep(3)

    # Summary
    _show_summary(results, not_found, failures, count)


def _show_summary(
    results: list[NextDNSResult],
    not_found: int,
    failures: int,
    total: int,
):
    """Display batch summary."""
    console.print()
    successful = len(results)
    if results:
        table = Table(
            title=f"Results Summary ({successful}/{total})",
            show_header=True,
        )
        table.add_column("#", style="dim", width=4)
        table.add_column("Email", style="cyan")
        table.add_column("API Key", style="yellow")
        table.add_column("Profile ID", style="magenta")
        table.add_column("Created (UTC)", style="dim")

        for i, r in enumerate(results, 1):
            # Format timestamp for display
            ts = r.created_at or ""
            if ts:
                # Extract just the datetime part for cleaner display
                ts = ts.replace("T", " ").split("+")[0][:19]
            table.add_row(
                str(i),
                r.email or "N/A",
                r.api_key[:8] + "..." if r.api_key else "N/A",
                r.profile_id or "N/A",
                ts,
            )

        console.print(table)
    else:
        console.print("[yellow]No successful registrations with API key found.[/yellow]")

    console.print(
        f"\n[green]Success (API key found):[/green] {successful}  "
        f"[yellow]Account registered (no API key):[/yellow] {not_found}  "
        f"[red]Failed:[/red] {failures}"
    )
    console.print(f"[dim]Results saved to {OUTPUT_FILE}[/dim]")


def main():
    parser = argparse.ArgumentParser(
        description="NextDNS Auto-Register Tool — Generate API keys using temp emails",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                      # Ask how many to generate
  python main.py --count 10          # Generate 10 directly
  python main.py -c 5 -o mykeys.txt  # Custom output file
  python main.py --visible           # Show browser window
  python main.py -c 3 --visible      # Batch with visible browser
        """,
    )
    parser.add_argument(
        "-c", "--count", type=int, default=0,
        help="Number of accounts to register (0 = interactive mode)",
    )
    parser.add_argument(
        "-o", "--output", type=str, default=OUTPUT_FILE,
        help=f"Output file path (default: {OUTPUT_FILE})",
    )
    parser.add_argument(
        "-p", "--password", type=str, default=None,
        help="Custom password for all accounts (default: random 14-char)",
    )
    parser.add_argument(
        "--visible", action="store_true",
        help="Show browser window (default: headless)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable verbose debug logging",
    )

    args = parser.parse_args()

    if args.verbose:
        import logging
        log.setLevel(logging.DEBUG)

    # If no count provided, ask interactively
    if args.count <= 0:
        console.print()
        try:
            user_input = console.input(
                "[cyan]How many API keys do you want to generate?[/cyan] (default: 1): "
            ).strip()
            if user_input:
                args.count = int(user_input)
            else:
                args.count = 1
        except (ValueError, EOFError):
            args.count = 1

    try:
        asyncio.run(run_batch(args.count, args.output, args.visible, args.password))
    except KeyboardInterrupt:
        console.print("\n[red]Interrupted by user.[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
