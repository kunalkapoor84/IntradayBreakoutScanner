import json, base64, os
from datetime import datetime
from typing import List
from config.settings import CONFIG
from config.logging_setup import setup_logging
from models import ScannerOutput, ScoredStock
from scoring.ai_scorer import AIScorer

logger = setup_logging("html_report")


def _stock_to_dict(s: ScoredStock, rank: int) -> dict:
    scorer = AIScorer()
    band = scorer.get_confidence_band(s.total_score)
    d = s.direction.value if hasattr(s.direction, "value") else str(s.direction)
    chart = ""
    if s.chart_path and os.path.exists(s.chart_path):
        try:
            with open(s.chart_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
                chart = f"data:image/png;base64,{b64}"
        except: pass
    return {
        "rank": rank, "symbol": s.symbol, "score": round(s.total_score, 1),
        "band": band, "confidence": round(s.confidence, 1), "direction": d,
        "cmp": s.cmp, "entry": s.entry_price, "sl": s.stop_loss,
        "t1": s.target_1, "t2": s.target_2, "atr": round(s.atr, 2),
        "volume_ratio": round(s.volume_ratio, 2), "rsi": round(s.rsi, 1),
        "adx": round(s.adx, 1), "sector": s.sector, "strategy": s.strategy,
        "pattern": s.pattern_detected, "rr": round(s.risk_reward, 2),
        "position_size": s.position_size, "catalyst": s.catalyst,
        "chart": chart, "bollinger_squeeze": bool(s.bollinger_squeeze),
        "nr_detected": bool(s.nr_detected),
        "breakout_proximity": round(s.breakout_proximity, 1),
        "expected_move_pct": round(s.expected_move_pct, 2),
    }


def generate_html(output: ScannerOutput) -> str:
    data = [_stock_to_dict(s, i + 1) for i, s in enumerate(output.top_stocks)]
    json_data = json.dumps(data)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Breakout Scanner - Top 20</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0f2f5; color: #333; padding: 20px; }}
.container {{ max-width: 1000px; margin: 0 auto; }}
.header {{ background: #1a237e; color: #fff; padding: 16px 24px; border-radius: 10px; margin-bottom: 20px; }}
.header h1 {{ font-size: 20px; }}
.header .meta {{ font-size: 13px; opacity: 0.8; margin-top: 4px; }}
.controls {{ display: flex; gap: 12px; align-items: center; margin-bottom: 16px; flex-wrap: wrap; }}
.controls label {{ font-weight: 600; font-size: 14px; }}
.controls select {{ padding: 8px 12px; border: 1px solid #ccc; border-radius: 6px; font-size: 14px; min-width: 200px; background: #fff; }}
.widget {{ background: #fff; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); padding: 20px; margin-bottom: 20px; }}
.widget h2 {{ font-size: 15px; color: #1a237e; margin-bottom: 14px; padding-bottom: 8px; border-bottom: 2px solid #e8eaf6; }}
.metrics {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 12px; }}
.metric {{ background: #f8f9fa; border-radius: 8px; padding: 12px; text-align: center; }}
.metric .label {{ font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 0.5px; }}
.metric .value {{ font-size: 18px; font-weight: 700; margin-top: 4px; }}
.metric .value.bullish {{ color: #26a69a; }}
.metric .value.bearish {{ color: #ef5350; }}
.metric .value.neutral {{ color: #ffa726; }}
.band {{ display: inline-block; padding: 2px 10px; border-radius: 4px; font-size: 13px; font-weight: 600; color: #fff; }}
.band-5 {{ background: #1b5e20; }}
.band-4 {{ background: #2e7d32; }}
.band-3 {{ background: #f57f17; }}
.band-2 {{ background: #e65100; }}
.band-1 {{ background: #78909c; }}
.tag {{ display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 11px; font-weight: 600; margin-right: 4px; }}
.tag-green {{ background: #e8f5e9; color: #2e7d32; }}
.tag-red {{ background: #ffebee; color: #c62828; }}
.tag-blue {{ background: #e3f2fd; color: #1565c0; }}
.tag-orange {{ background: #fff3e0; color: #e65100; }}
.chart-wrap {{ text-align: center; }}
.chart-wrap img {{ max-width: 100%; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
.no-chart {{ padding: 40px; text-align: center; color: #999; font-size: 14px; background: #f8f9fa; border-radius: 8px; }}
.empty {{ padding: 40px; text-align: center; color: #999; font-size: 15px; }}
.description {{ font-size: 13px; color: #555; line-height: 1.6; margin-top: 12px; padding: 12px; background: #f8f9fa; border-radius: 6px; border-left: 3px solid #1a237e; }}
.chart-placeholder {{ display: flex; align-items: center; justify-content: center; height: 400px; background: #f8f9fa; border-radius: 8px; color: #999; font-size: 14px; border: 2px dashed #ddd; }}
@media (max-width: 600px) {{ .metrics {{ grid-template-columns: repeat(2, 1fr); }} }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>Intraday Breakout Scanner — Top 20</h1>
    <div class="meta">Generated: {ts}</div>
  </div>
  <div class="controls">
    <label for="stockSelect">Select Stock:</label>
    <select id="stockSelect"></select>
    <span id="rankBadge" style="font-size:13px;color:#666;"></span>
  </div>
  <div id="techWidget" class="widget" style="display:none">
    <h2>Technical Summary</h2>
    <div class="metrics" id="metrics"></div>
    <div class="description" id="description"></div>
  </div>
  <div id="chartWidget" class="widget" style="display:none">
    <h2>Chart</h2>
    <div class="chart-wrap" id="chartWrap"></div>
  </div>
  <div id="emptyState" class="empty">Select a stock from the dropdown to view details.</div>
</div>
<script>
const stocks = {json_data};
const sel = document.getElementById('stockSelect');
const empty = document.getElementById('emptyState');
const techW = document.getElementById('techWidget');
const chartW = document.getElementById('chartWidget');
const metrics = document.getElementById('metrics');
const desc = document.getElementById('description');
const chartWrap = document.getElementById('chartWrap');
const rankBadge = document.getElementById('rankBadge');

stocks.forEach(s => {{
  const o = document.createElement('option');
  o.value = s.symbol;
  o.textContent = s.symbol;
  sel.appendChild(o);
}});

sel.addEventListener('change', function() {{
  const sym = this.value;
  if (!sym) {{ empty.style.display = 'block'; techW.style.display = 'none'; chartW.style.display = 'none'; return; }}
  empty.style.display = 'none';
  techW.style.display = 'block';
  chartW.style.display = 'block';
  const s = stocks.find(st => st.symbol === sym);
  renderTech(s);
  renderChart(s);
}});
if (stocks.length > 0) {{
  sel.value = stocks[0].symbol;
  sel.dispatchEvent(new Event('change'));
}}
function renderTech(s) {{
  rankBadge.textContent = '#' + s.rank + ' of ' + stocks.length;
  const dirClass = s.direction.toLowerCase();
  const bandClass = s.band === '*****' ? 'band-5' : s.band === '****' ? 'band-4' : s.band === '***' ? 'band-3' : s.band === '**' ? 'band-2' : 'band-1';
  metrics.innerHTML = `
    <div class="metric"><div class="label">Score</div><div class="value">${{s.score}}</div></div>
    <div class="metric"><div class="label">Band</div><div class="value"><span class="band ${{bandClass}}">${{s.band}}</span></div></div>
    <div class="metric"><div class="label">Direction</div><div class="value ${{dirClass}}">${{s.direction}}</div></div>
    <div class="metric"><div class="label">Confidence</div><div class="value">${{s.confidence}}%</div></div>
    <div class="metric"><div class="label">CMP</div><div class="value">₹${{s.cmp.toFixed(2)}}</div></div>
    <div class="metric"><div class="label">Entry</div><div class="value">₹${{s.entry.toFixed(2)}}</div></div>
    <div class="metric"><div class="label">SL</div><div class="value">₹${{s.sl.toFixed(2)}}</div></div>
    <div class="metric"><div class="label">T1</div><div class="value">₹${{s.t1.toFixed(2)}}</div></div>
    <div class="metric"><div class="label">T2</div><div class="value">₹${{s.t2.toFixed(2)}}</div></div>
    <div class="metric"><div class="label">ATR</div><div class="value">₹${{s.atr.toFixed(2)}}</div></div>
    <div class="metric"><div class="label">ATR%</div><div class="value">${{(s.atr/s.cmp*100).toFixed(2)}}%</div></div>
    <div class="metric"><div class="label">RSI</div><div class="value">${{s.rsi}}</div></div>
    <div class="metric"><div class="label">ADX</div><div class="value">${{s.adx}}</div></div>
    <div class="metric"><div class="label">Vol Ratio</div><div class="value">${{s.volume_ratio.toFixed(2)}}x</div></div>
    <div class="metric"><div class="label">R:R</div><div class="value">${{s.rr.toFixed(2)}}</div></div>
    <div class="metric"><div class="label">Pos Size</div><div class="value">${{s.position_size}}</div></div>
    <div class="metric"><div class="label">Exp Move%</div><div class="value">${{s.expected_move_pct.toFixed(2)}}%</div></div>
  `;
  let tags = '';
  if (s.bollinger_squeeze) tags += '<span class="tag tag-orange">BB-SQZ</span>';
  if (s.nr_detected) tags += '<span class="tag tag-blue">NR</span>';
  if (s.breakout_proximity <= 2) tags += '<span class="tag tag-green">BRK-' + s.breakout_proximity + '%</span>';
  desc.innerHTML = `
    <strong>${{s.symbol}}</strong> &middot; ${{s.sector}} &middot; ${{s.strategy}}<br>
    Pattern: ${{s.pattern || 'N/A'}}<br>
    Catalyst: ${{s.catalyst}}<br>
    ${{tags}}
  `;
}}
function renderChart(s) {{
  if (s.chart) {{
    chartWrap.innerHTML = '<img src="' + s.chart + '" alt="Chart for ' + s.symbol + '" onerror="this.parentNode.innerHTML=\\'<div class=no-chart>Chart image not found</div>\\'">';
  }} else {{
    chartWrap.innerHTML = '<div class="no-chart">No chart available for this stock.</div>';
  }}
}}
</script>
</body>
</html>"""
    return html


class HTMLReportGenerator:
    def generate(self, output: ScannerOutput, filepath: str = ""):
        if not filepath:
            filepath = f"{CONFIG.output_dir}\\reports\\scanner_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        html = generate_html(output)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"HTML saved: {filepath}")
        return filepath
