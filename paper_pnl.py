from pathlib import Path
import csv

LOG_FILE = Path("/Users/Owner/weather_ai/trade_log.csv")

def to_float(x, default=0.0):
    try:
        return float(str(x).strip())
    except:
        return default

def main():
    if not LOG_FILE.exists():
        print("trade_log.csv not found")
        return

    rows = list(csv.DictReader(LOG_FILE.open(encoding="utf-8")))
    if len(rows) < 2:
        print("not enough rows")
        return

    prev = rows[-2]
    curr = rows[-1]

    prev_nikkei_alloc = to_float(prev["nikkei_alloc"])
    prev_semi_alloc = to_float(prev["semi_alloc"])
    prev_capital = to_float(prev["capital"])

    prev_nikkei_price = to_float(prev["nikkei_ref_price"])
    prev_semi_price = to_float(prev["semi_ref_price"])
    curr_nikkei_price = to_float(curr["nikkei_ref_price"])
    curr_semi_price = to_float(curr["semi_ref_price"])

    if prev_nikkei_price <= 0 or prev_semi_price <= 0 or curr_nikkei_price <= 0 or curr_semi_price <= 0:
        print("price missing")
        return

    nikkei_return = (curr_nikkei_price - prev_nikkei_price) / prev_nikkei_price
    semi_return = (curr_semi_price - prev_semi_price) / prev_semi_price

    # allocがマイナスならショート、プラスならロング
    strategy_return = (prev_nikkei_alloc * nikkei_return) + (prev_semi_alloc * semi_return)
    paper_pnl = round(prev_capital * strategy_return, 2)

    rows[-2]["paper_pnl"] = str(paper_pnl)

    with LOG_FILE.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "date","score","total_position","nikkei_alloc","semi_alloc",
                "capital","nikkei_ref_price","semi_ref_price","paper_pnl"
            ]
        )
        writer.writeheader()
        writer.writerows(rows)

    print("updated paper_pnl:", paper_pnl)

if __name__ == "__main__":
    main()
