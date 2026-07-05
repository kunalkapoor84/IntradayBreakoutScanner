import csv
from datetime import datetime
from config.settings import CONFIG
from config.logging_setup import setup_logging
from models import ScannerOutput

logger = setup_logging("csv_report")


class CSVReportGenerator:
    def generate(self, output: ScannerOutput, filepath: str = ""):
        if not filepath:
            filepath = f"{CONFIG.output_dir}\\reports\\scanner_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        fn = ["Rank","Symbol","Score","Conf%","Direction","Entry_Price","Stop_Loss","Target_1","Target_2","ATR","Volume_Ratio","RSI","ADX","PCR","OI_Change","IV","Sector","Strategy","Pattern","Exp_Move%","R:R","Pos_Size","Catalyst"]
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fn); w.writeheader()
            for r, s in enumerate(output.top_stocks, 1):
                w.writerow({"Rank":r,"Symbol":s.symbol,"Score":round(s.total_score,1),"Conf%":round(s.confidence,1),
                           "Direction":s.direction.value if hasattr(s.direction,'value') else s.direction,
                           "Entry_Price":s.entry_price,"Stop_Loss":s.stop_loss,"Target_1":s.target_1,"Target_2":s.target_2,
                           "ATR":round(s.atr,2),"Volume_Ratio":round(s.volume_ratio,2),"RSI":round(s.rsi,1),
                           "ADX":round(s.adx,1),"PCR":round(s.pcr,2),"OI_Change":s.oi_change,"IV":round(s.iv,1),
                           "Sector":s.sector,"Strategy":s.strategy,"Pattern":s.pattern_detected,
                           "Exp_Move%":round(s.expected_move_pct,2),"R:R":round(s.risk_reward,2),
                           "Pos_Size":s.position_size,"Catalyst":s.catalyst})
        logger.info(f"CSV saved: {filepath}")
        return filepath
