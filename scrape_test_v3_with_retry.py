#!/usr/bin/env python3
"""scrape_test_v3 + 二次采集"""
import argparse
import datetime
import json
import os

from playwright.sync_api import sync_playwright

from scrape_test_v3 import scrape_with_retry, RESULT_FILE


def main():
    parser = argparse.ArgumentParser(description="CSQAQ 抓取 V3 + 二次采集")
    parser.add_argument("--items-json", default="", help="批量 JSON 数组")
    args = parser.parse_args()

    print("=" * 60, flush=True)
    print("  CSQAQ 抓取 V3（expect_response + 二次采集）", flush=True)
    print("=" * 60, flush=True)

    items = []
    if args.items_json:
        try:
            items = json.loads(args.items_json)
        except json.JSONDecodeError as e:
            print(f"[ERROR] items_json 解析失败: {e}", flush=True)
            return
    else:
        print("[ERROR] 未提供 items_json", flush=True)
        return

    print(f"  饰品数量: {len(items)}", flush=True)

    results = []
    start_time = datetime.datetime.now()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            context = browser.new_context(
                viewport={"width": 1400, "height": 900},
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="zh-CN",
            )
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = context.new_page()

            # 第一轮采集
            print(f"\n  第一轮采集", flush=True)
            for idx, item in enumerate(items):
                print(f"  进度: {idx+1}/{len(items)} - {item.get('name', 'N/A')}", flush=True)
                result = scrape_with_retry(page, item["goods_id"], item.get("name"))
                results.append(result)

            first_success = sum(1 for r in results if r["scrape_ok"])
            first_failed = len(results) - first_success
            print(f"\n  第一轮: {first_success}/{len(items)} 成功, {first_failed} 失败", flush=True)

            # 第二轮采集（对失败饰品）
            if first_failed > 0:
                print(f"\n  第二轮采集（{first_failed} 个失败饰品）", flush=True)
                for idx, result in enumerate(results):
                    if not result["scrape_ok"]:
                        goods_id = result["goods_id"]
                        name = result.get("name", "")
                        print(f"  重采: {name} (goods_id={goods_id})", flush=True)
                        new_result = scrape_with_retry(page, goods_id, name)
                        if new_result["scrape_ok"]:
                            results[idx] = new_result
                            print(f"  → ✓ 重采成功", flush=True)
                        else:
                            print(f"  → ✗ 重采仍失败", flush=True)

            browser.close()

    except Exception as e:
        print(f"\n[FATAL] {type(e).__name__}: {e}", flush=True)

    end_time = datetime.datetime.now()
    duration = (end_time - start_time).total_seconds()

    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False)

    success_count = sum(1 for r in results if r["scrape_ok"])
    print(f"\n{'='*60}", flush=True)
    print(f"  最终汇总: {success_count}/{len(items)} 成功, 耗时 {duration:.0f}s", flush=True)


if __name__ == "__main__":
    main()
