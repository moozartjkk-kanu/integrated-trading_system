# -*- coding: utf-8 -*-
"""
키움증권 자동매매 시스템 - 메인 GUI
"""
import sys
import datetime
from collections import deque
import time  # ✅ 추가: 로그 스팸/쓰로틀용

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTabWidget,
    QMessageBox, QHeaderView, QFrame, QGridLayout, QInputDialog, QDialog, QProgressBar,
    QScrollArea, QRadioButton, QButtonGroup, QCheckBox
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor


class DisclaimerDialog(QDialog):
    """이용 약관 동의 다이얼로그 (스크롤 끝까지 내려야 체크박스 활성화)"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("중요 안내 사항")
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.CustomizeWindowHint)
        self.setModal(True)
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setPlainText(
            "*프로그램 이용 시 필독사항*\n\n"
            "본 프로그램은 투자 도구로 제공되는 소프트웨어이며\n"
            "특정 종목에 대한 매수 또는 매도를 권유하거나\n"
            "투자 자문을 제공하지 않습니다.\n\n"
            "본 프로그램은 사용자가 선택한 종목에 대해\n"
            "사전에 설정된 기술적 조건에 따라 자동 주문 기능을 수행합니다.\n\n"
            "투자에 대한 최종 판단과 책임은 전적으로 사용자 본인에게 있습니다.\n\n"
            "본 프로그램은 수익을 보장하지 않으며\n"
            "투자 결과에 따라 손실이 발생할 수 있습니다.\n\n"
            "프로그램 사용으로 발생하는 모든 투자 결과 및 손익에 대한 책임은\n"
            "사용자 본인에게 있으며 프로그램 제공자는 이에 대해 어떠한 책임도 부담하지 않습니다.\n\n"
            "종목 선택 및 투자 금액 설정은 사용자 본인이 직접 수행해야 합니다.\n\n"
            "**하락 혹은 급락장에는 손절이(매도 설정) 없으므로 유의해야합니다.**\n"
            "=>익절 혹은 자동 매도를 한번이라도 진행한 종목에 대해서는 손절이 로직이 존재하지만\n"
            "매도가 한번도 진행되지 않은 종목은 추가매수만 있으며, 하락 혹은 급락장에서의 매도(손절) 설정은 없으므로 주의바랍니다.\n\n"
            "**정규장 이외의 시간이면서 NXT거래소 거래 가능 시간대에는 NXT거래소로 주문이 걸립니다.**\n\n"
            "***프로그램 이용은 위 내용을 충분히 이해하고 동의한 것으로 간주됩니다.***"
        )
        self.text.setMinimumHeight(260)
        self.text.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)
        layout.addWidget(self.text)

        self.scroll_hint_label = QLabel("↓ 내용을 끝까지 스크롤해야 동의할 수 있습니다.")
        self.scroll_hint_label.setStyleSheet("color: #e65100; font-size: 9pt;")
        layout.addWidget(self.scroll_hint_label)

        from PyQt5.QtWidgets import QCheckBox
        self.agree_checkbox = QCheckBox("위 내용을 모두 읽었으며 동의합니다.")
        font = QFont()
        font.setBold(True)
        font.setPointSize(10)
        self.agree_checkbox.setFont(font)
        self.agree_checkbox.setEnabled(False)
        self.agree_checkbox.stateChanged.connect(self._on_checkbox_changed)
        layout.addWidget(self.agree_checkbox)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.ok_btn = QPushButton("확인")
        self.ok_btn.setEnabled(False)
        self.ok_btn.setMinimumWidth(100)
        self.ok_btn.setStyleSheet(
            "QPushButton:enabled { background-color: #4CAF50; color: white; font-weight: bold; }"
            "QPushButton:disabled { background-color: #cccccc; color: #888888; }"
        )
        self.ok_btn.clicked.connect(self.accept)

        cancel_btn = QPushButton("취소 (종료)")
        cancel_btn.setMinimumWidth(100)
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(self.ok_btn)
        layout.addLayout(btn_layout)

    def _on_scroll_changed(self, value):
        """스크롤이 끝(최대값)에 도달하면 체크박스 활성화"""
        scrollbar = self.text.verticalScrollBar()
        if value >= scrollbar.maximum():
            self.agree_checkbox.setEnabled(True)
            self.scroll_hint_label.setText("✔ 내용을 모두 확인했습니다. 아래에 동의해 주세요.")
            self.scroll_hint_label.setStyleSheet("color: #2e7d32; font-size: 9pt;")

    def _on_checkbox_changed(self, state):
        self.ok_btn.setEnabled(state == Qt.Checked)

    def closeEvent(self, event):
        self.reject()
        event.accept()


class ScanProgressDialog(QDialog):
    """스캔 진행 상황 팝업 (비모달, 항상 최상위)"""

    def __init__(self, cancel_callback, parent=None):
        super().__init__(parent)
        self._cancel_cb = cancel_callback
        self.setWindowTitle("종목 탐색 중...")
        self.setWindowFlags(
            Qt.Window | Qt.WindowTitleHint | Qt.CustomizeWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setFixedWidth(440)
        self.setModal(False)

        v = QVBoxLayout(self)
        v.setSpacing(10)
        v.setContentsMargins(16, 14, 16, 12)

        self._phase_lbl = QLabel("준비 중...")
        f = QFont(); f.setBold(True); f.setPointSize(11)
        self._phase_lbl.setFont(f)
        v.addWidget(self._phase_lbl)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setFormat("0 / 0")
        self._bar.setFixedHeight(22)
        v.addWidget(self._bar)

        self._name_lbl = QLabel("")
        self._name_lbl.setStyleSheet("color:#555; font-size:9pt;")
        self._name_lbl.setAlignment(Qt.AlignCenter)
        v.addWidget(self._name_lbl)

        self._cache_lbl = QLabel("")
        self._cache_lbl.setStyleSheet("color:#1565C0; font-size:9pt;")
        self._cache_lbl.setAlignment(Qt.AlignCenter)
        v.addWidget(self._cache_lbl)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._cancel_btn = QPushButton("취소")
        self._cancel_btn.setMinimumWidth(90)
        self._cancel_btn.setStyleSheet("background:#f44336; color:white; font-weight:bold;")
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self._cancel_btn)
        v.addLayout(btn_row)

    def update(self, phase, done, total, name):
        self._phase_lbl.setText(phase)
        if total > 0:
            self._bar.setMaximum(total)
            self._bar.setValue(done)
            pct = int(done / total * 100)
            self._bar.setFormat(f"{done} / {total}  ({pct}%)")
        self._name_lbl.setText(name)

    def set_cache_info(self, cached, total):
        if cached > 0:
            self._cache_lbl.setText(f"캐시 재사용 {cached}개 / 신규 TR 조회 {total}개")
        else:
            self._cache_lbl.setText("")

    def mark_done(self):
        self._phase_lbl.setText("탐색 완료")
        self._bar.setFormat("완료")
        self._name_lbl.setText("")
        self._cancel_btn.setText("닫기")
        self._cancel_btn.setStyleSheet("background:#4CAF50; color:white; font-weight:bold;")
        try:
            self._cancel_btn.clicked.disconnect()
        except Exception:
            pass
        self._cancel_btn.clicked.connect(self.hide)

    def _on_cancel(self):
        if self._cancel_cb:
            self._cancel_cb()
        self.hide()

    def closeEvent(self, e):
        self._on_cancel()
        e.ignore()


class WatchlistLoadingDialog(QDialog):
    """감시 종목 데이터 불러오는 중 알림창 (진행률 표시)"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("불러오는 중")
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.CustomizeWindowHint)
        self.setModal(True)
        self.setFixedSize(340, 110)
        layout = QVBoxLayout()
        layout.setSpacing(8)

        self._label = QLabel("감시 종목 리스트 불러오는 중...", self)
        self._label.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(11)
        self._label.setFont(font)
        layout.addWidget(self._label)

        self._progress_bar = QProgressBar(self)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        layout.addWidget(self._progress_bar)

        self._percent_label = QLabel("0 / 0  (0%)", self)
        self._percent_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._percent_label)

        self.setLayout(layout)

    def update_progress(self, done, total):
        """진행률 업데이트"""
        if total <= 0:
            return
        pct = int(done / total * 100)
        self._progress_bar.setValue(pct)
        self._percent_label.setText(f"{done} / {total}  ({pct}%)")

    def closeEvent(self, event):
        event.ignore()  # 사용자가 닫기 버튼으로 닫지 못하도록


class StockSearchWorker(QThread):
    """백그라운드 종목 검색 워커 (UI 프리징 방지)"""
    search_finished = pyqtSignal(list)  # [(code, name), ...]
    search_error = pyqtSignal(str)

    def __init__(self, kiwoom, search_text):
        super().__init__()
        self.kiwoom = kiwoom
        self.search_text = search_text

    def run(self):
        try:
            results = self.kiwoom.find_stocks_by_name(self.search_text)
            self.search_finished.emit(results)
        except Exception as e:
            self.search_error.emit(str(e))


class StockCacheLoaderWorker(QThread):
    """백그라운드 종목 캐시 로더 (로그인 직후 사용)"""
    load_finished = pyqtSignal(bool, int)  # (success, count)

    def __init__(self, kiwoom):
        super().__init__()
        self.kiwoom = kiwoom

    def run(self):
        try:
            success = self.kiwoom.load_stock_cache()
            count = len(self.kiwoom._stock_cache) if success else 0
            self.load_finished.emit(success, count)
        except Exception as e:
            print(f"[종목캐시] 로딩 오류: {e}")
            self.load_finished.emit(False, 0)

from config import Config
from kiwoom_api import KiwoomAPI
from trading_logic import AutoTrader
from technical_analysis import TechnicalAnalysis

import os as _os
import importlib.util as _ilu

# ── 종목 탐색 모듈 동적 로드 ──────────────────────────────────────────────────
_SEARCH_DIR = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'search_engine')
_SCANNER_AVAILABLE = False
StockScanner = None
ScanConfig = None

try:
    def _load_search_mod(name, filename):
        spec = _ilu.spec_from_file_location(name, _os.path.join(_SEARCH_DIR, filename))
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    _search_ta  = _load_search_mod('_search_ta',  'technical_analysis.py')
    _search_cfg = _load_search_mod('_search_cfg', 'config.py')
    ScanConfig  = _search_cfg.Config

    _orig_ta = sys.modules.get('technical_analysis')
    sys.modules['technical_analysis'] = _search_ta
    try:
        _search_scanner = _load_search_mod('_search_scanner', 'scanner.py')
        StockScanner = _search_scanner.Scanner
        _SCANNER_AVAILABLE = True
    finally:
        if _orig_ta is not None:
            sys.modules['technical_analysis'] = _orig_ta
        else:
            sys.modules.pop('technical_analysis', None)
except Exception as _e:
    print(f"[경고] 종목 탐색 모듈 로드 실패: {_e}")
# ─────────────────────────────────────────────────────────────────────────────


class MainWindow(QMainWindow):
    """메인 윈도우"""

    def __init__(self):
        super().__init__()
        self.config = Config()
        self.kiwoom = None
        self.trader = None
        self.ta = TechnicalAnalysis()

        # 종목 탐색 설정 (init_ui 전에 초기화 필요)
        self.scan_config = ScanConfig() if _SCANNER_AVAILABLE else None
        self.scanner = None
        self._scan_progress_dlg = None
        self._scan_result_cache = {}

        self.init_ui()

        # 종목 탐색 카운트다운 타이머
        self._scan_countdown_timer = QTimer()
        self._scan_countdown_timer.timeout.connect(self._tick_scan_countdown)

        # ✅ 로그 버퍼링 (UI 프리징 방지)
        self._log_buffer = deque(maxlen=5000)
        self._log_flush_timer = QTimer()
        self._log_flush_timer.timeout.connect(self._flush_log_buffer)
        self._log_flush_timer.start(200)

        # ✅ 주문 큐 처리 타이머 (주문은 메인(UI) 스레드에서만)
        self.order_timer = QTimer()
        self.order_timer.timeout.connect(self._drain_order_queue)
        # 자동매매 시작 시에만 start()


        # ✅ 타이머 겹침(중복 실행) 방지 플래그 (필수)
        self._is_refreshing_watchlist = False
        self._is_checking_signals = False

        # ✅ 정지 처리중 플래그 (필수: stop 중 교착/응답없음 방지)
        self._is_stopping = False

        # ✅ 로그 스팸 방지용 (권장)
        self._last_watchlist_log_ts = 0.0

        # ✅ 비동기 워치리스트 갱신용 큐
        self._watchlist_refresh_queue = []
        self._watchlist_refresh_period = 20
        self._watchlist_refresh_percent = 19
        self._watchlist_refresh_total = 0
        self._watchlist_refresh_done = 0
        self._watchlist_refresh_generation = 0
        self._watchlist_refresh_pending_codes = set()
        self._watchlist_loading_dialog = None
        self._holdings_refresh_inflight = False

        # ✅ 워치리스트 헤더를 설정값으로 반영 (권장)
        self._update_watchlist_header()

        # 자동 갱신 타이머 (잔고 갱신: 60초)
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_data)

        # 감시 종목 갱신 타이머 (10분 주기 - TR 호출 최소화)
        self.watchlist_refresh_timer = QTimer()
        self.watchlist_refresh_timer.timeout.connect(self.refresh_watchlist)

        # 자동매매 체크 타이머
        self.trading_timer = QTimer()
        self.trading_timer.timeout.connect(self.check_trading_signals)

        # ✅ 장 열림 감지 타이머 (주문 복원 자동 호출용)
        self._orders_restored_today = False
        self._last_market_open_check_date = None
        self._restore_retry_scheduled = False
        self.market_open_timer = QTimer()
        self.market_open_timer.timeout.connect(self._check_market_open_and_restore)
        self.market_open_timer.start(60000)  # 1분마다 체크

        # ✅ 실시간 UI 업데이트용 행 매핑 (code → row)
        self._holdings_code_to_row = {}
        self._watchlist_code_to_row = {}
        self._watchlist_rt_screens = ["2000", "2001"]
        self._watchlist_rt_registered = False
        self._watchlist_rt_refresh_timer = QTimer()
        self._watchlist_rt_refresh_timer.setSingleShot(True)
        self._watchlist_rt_refresh_timer.timeout.connect(self._register_watchlist_realtime)

        self._scan_table_refresh_timer = QTimer()
        self._scan_table_refresh_timer.setSingleShot(True)
        self._scan_table_refresh_timer.timeout.connect(self._drain_scan_table_refresh)
        self._scan_table_refresh_generation = 0
        self._scan_table_refresh_rows = []
        self._scan_table_refresh_index = 0
        self._scan_table_refresh_batch_size = 30
        self._scan_table_refresh_cfg = {}

        # ✅ 잔고 변경 디바운스 타이머 (과도한 TR 호출 방지)
        self._balance_changed_timer = QTimer()
        self._balance_changed_timer.setSingleShot(True)
        self._balance_changed_timer.timeout.connect(self.refresh_holdings)

        # ✅ 백그라운드 검색 워커 (UI 프리징 방지)
        self._search_worker = None
        self._cache_loader_worker = None
        self._pending_search_callback = None

        # 초기 감시 종목 로드 (로그인 전에도 목록 표시)
        QTimer.singleShot(100, self._load_initial_watchlist)

    # =========================
    # 공용 유틸
    # =========================
    def _update_watchlist_header(self):
        """워치리스트 테이블 헤더에 현재 main condition 설정값 반영 (권장)"""
        try:
            percent = self.config.get("buy", "main_condition_percent") or 19
        except Exception:
            percent = 19

        headers = ["종목코드", "종목명", "현재가", "메인 기준", f"main condition"]
        if hasattr(self, "watchlist_table") and self.watchlist_table is not None:
            self.watchlist_table.setHorizontalHeaderLabels(headers)

    def _fmt_int_or_dash(self, v):
        """None/비정상 값 포맷팅 안전 처리 (필수: 크래시 방지)"""
        try:
            if v is None:
                return "-"
            return f"{int(v):,}"
        except Exception:
            return "-"

    def _schedule_watchlist_realtime_registration(self, delay_ms=150):
        """감시종목 실시간 재등록을 짧게 디바운스한다."""
        if not self.kiwoom or not self.kiwoom.is_connected():
            return
        self._watchlist_rt_refresh_timer.start(delay_ms)

    def _append_watchlist_row(self, code, name):
        """감시종목 테이블에 새 행을 추가한다."""
        row = self.watchlist_table.rowCount()
        self.watchlist_table.setRowCount(row + 1)
        self._watchlist_code_to_row[code] = row
        self.watchlist_table.setItem(row, 0, QTableWidgetItem(code))
        self.watchlist_table.setItem(row, 1, QTableWidgetItem(name))
        self.watchlist_table.setItem(row, 2, QTableWidgetItem("-"))
        self.watchlist_table.setItem(row, 3, QTableWidgetItem("-"))
        self.watchlist_table.setItem(row, 4, QTableWidgetItem("-"))
        return row

    def _schedule_scan_table_refresh(self):
        if not hasattr(self, 'sc_result_table'):
            return

        self._scan_table_refresh_timer.stop()
        self._scan_table_refresh_generation += 1
        self._scan_table_refresh_rows = list(self._scan_result_cache.values())
        self._scan_table_refresh_index = 0
        self._scan_table_refresh_cfg = self.scan_config.get_scan() if self.scan_config else {}

        self.sc_result_table.setSortingEnabled(False)
        self.sc_result_table.clearContents()
        self.sc_result_table.setRowCount(len(self._scan_table_refresh_rows))
        self._scan_table_refresh_timer.start(0)

    def _populate_scan_result_row(self, r_idx, row, scan_cfg):
        code = row.get("code", "")
        name = row.get("name", "")
        price = row.get("price", 0)
        rsi = row.get("rsi")
        ma = row.get("ma")
        ma_s = row.get("ma_short")
        vr = row.get("volume_ratio")
        bo = row.get("breakout", False)
        supply_ok = row.get("supply_ok", False)
        supply_data_available = row.get("supply_data_available", True)
        tv = row.get("trading_value")
        tv_ratio = row.get("trading_value_ratio")

        self._sc_set(r_idx, 0, f"{name} ({code})")
        self._sc_set(
            r_idx, 1, f"{int(price):,}" if price else "-",
            align=Qt.AlignRight | Qt.AlignVCenter,
        )

        rsi_txt = f"{rsi:.1f}" if rsi is not None else "-"
        item_rsi = self._sc_make_item(rsi_txt, align=Qt.AlignCenter)
        if rsi is not None:
            if rsi <= 30:
                item_rsi.setForeground(QColor("#1565C0"))
            elif rsi >= 70:
                item_rsi.setForeground(QColor("#c62828"))
        self.sc_result_table.setItem(r_idx, 2, item_rsi)

        if ma_s is not None and ma is not None:
            ma_txt = f"단{int(ma_s):,} / 장{int(ma):,}"
        elif ma is not None:
            dir_txt = "↑" if price > ma else "↓"
            ma_txt = f"{int(ma):,} {dir_txt}"
        else:
            ma_txt = "-"
        self._sc_set(r_idx, 3, ma_txt, align=Qt.AlignCenter)

        vr_txt = f"{vr:.1f}x" if vr is not None else "-"
        item_vr = self._sc_make_item(vr_txt, align=Qt.AlignCenter)
        if vr is not None and vr >= float(scan_cfg.get("volume_ratio") or 2):
            item_vr.setForeground(QColor("#e65100"))
        self.sc_result_table.setItem(r_idx, 4, item_vr)

        bo_txt = "●" if bo else "-"
        item_bo = self._sc_make_item(bo_txt, align=Qt.AlignCenter)
        if bo:
            item_bo.setForeground(QColor("#2e7d32"))
        self.sc_result_table.setItem(r_idx, 5, item_bo)

        supply_enabled = bool(scan_cfg.get("supply_enabled"))
        if not supply_enabled:
            supply_txt, supply_color = "-", None
        elif not supply_data_available:
            supply_txt, supply_color = "?", QColor("#ef6c00")
        elif supply_ok:
            supply_txt, supply_color = "●", QColor("#6a1b9a")
        else:
            supply_txt, supply_color = "✕", QColor("#9e9e9e")
        item_sup = self._sc_make_item(supply_txt, align=Qt.AlignCenter)
        if supply_color:
            item_sup.setForeground(supply_color)
        self.sc_result_table.setItem(r_idx, 6, item_sup)

        tv_enabled = bool(scan_cfg.get("trading_value_enabled"))
        if not tv_enabled or tv is None:
            tv_txt = "-"
        else:
            tv_bil = tv / 100
            tv_txt = f"{tv_bil:,.0f}억 ({tv_ratio:.0f}%)" if tv_ratio is not None else f"{tv_bil:,.0f}억"
        item_tv = self._sc_make_item(tv_txt, align=Qt.AlignRight | Qt.AlignVCenter)
        if tv_enabled and row.get("trading_value_ok"):
            item_tv.setForeground(QColor("#1565C0"))
        self.sc_result_table.setItem(r_idx, 7, item_tv)

        conds = []
        if row.get("rsi_ok"):
            conds.append("RSI")
        if row.get("ma_ok"):
            conds.append("MA")
        if row.get("volume_ok"):
            conds.append("거래량")
        if row.get("breakout"):
            conds.append("돌파")
        if row.get("supply_ok"):
            conds.append("수급")
        if row.get("trading_value_ok"):
            conds.append("거래대금")
        self._sc_set(r_idx, 8, " / ".join(conds) if conds else "-")

    def _drain_scan_table_refresh(self):
        if not hasattr(self, 'sc_result_table'):
            return

        rows = self._scan_table_refresh_rows
        if not rows:
            self.sc_result_table.setSortingEnabled(True)
            return

        end = min(
            self._scan_table_refresh_index + self._scan_table_refresh_batch_size,
            len(rows),
        )
        self.sc_result_table.setUpdatesEnabled(False)
        try:
            for r_idx in range(self._scan_table_refresh_index, end):
                self._populate_scan_result_row(
                    r_idx,
                    rows[r_idx],
                    self._scan_table_refresh_cfg,
                )
        finally:
            self.sc_result_table.setUpdatesEnabled(True)

        self._scan_table_refresh_index = end
        if self._scan_table_refresh_index < len(rows):
            self._scan_table_refresh_timer.start(0)
            return

        self.sc_result_table.setSortingEnabled(True)
        self.sc_result_table.viewport().update()

    def _load_initial_watchlist(self):
        """프로그램 시작 시 저장된 감시 종목 목록 로드 (가격 정보 제외)"""
        watchlist = self.config.get_watchlist()
        self.watchlist_table.setRowCount(len(watchlist))

        self._watchlist_code_to_row = {}
        for row, stock in enumerate(watchlist):
            code = stock["code"]
            name = stock.get("name", "")
            self._watchlist_code_to_row[code] = row
            self.watchlist_table.setItem(row, 0, QTableWidgetItem(code))
            self.watchlist_table.setItem(row, 1, QTableWidgetItem(name))
            self.watchlist_table.setItem(row, 2, QTableWidgetItem("-"))
            self.watchlist_table.setItem(row, 3, QTableWidgetItem("-"))
            self.watchlist_table.setItem(row, 4, QTableWidgetItem("-"))

        if watchlist:
            self.log(f"[시스템] 저장된 감시 종목 {len(watchlist)}개 로드 완료")

    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle("매매 보조 도구 시스템")
        self.setGeometry(100, 100, 1400, 900)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        top_frame = self.create_top_frame()
        main_layout.addWidget(top_frame)

        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)

        trading_tab = self.create_trading_tab()
        tab_widget.addTab(trading_tab, "매매 관리")

        watchlist_tab = self.create_watchlist_tab()
        tab_widget.addTab(watchlist_tab, "종목 관리")

        settings_tab = self.create_settings_tab()
        tab_widget.addTab(settings_tab, "설정")

        if _SCANNER_AVAILABLE and self.scan_config is not None:
            scan_settings_tab = self.create_scan_settings_tab()
            tab_widget.addTab(scan_settings_tab, "종목 스캔 설정")

            scan_results_tab = self.create_scan_results_tab()
            tab_widget.addTab(scan_results_tab, "탐색 종목")

        log_frame = self.create_log_frame()
        main_layout.addWidget(log_frame)

    def create_top_frame(self):
        """상단 프레임 (연결 상태, 계좌 정보)"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.StyledPanel)
        layout = QHBoxLayout(frame)

        self.status_label = QLabel("연결 상태: 미연결")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(self.status_label)

        self.login_btn = QPushButton("로그인")
        self.login_btn.clicked.connect(self.do_login)
        layout.addWidget(self.login_btn)

        layout.addWidget(QLabel("  |  "))

        layout.addWidget(QLabel("계좌:"))
        self.account_combo = QComboBox()
        self.account_combo.setMinimumWidth(150)
        self.account_combo.currentTextChanged.connect(self.on_account_changed)
        layout.addWidget(self.account_combo)

        layout.addWidget(QLabel("  |  "))

        self.balance_label = QLabel("예수금: -")
        layout.addWidget(self.balance_label)

        layout.addStretch()

        self.auto_trade_btn = QPushButton("자동매매 시작")
        self.auto_trade_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold; padding: 10px 20px;"
        )
        self.auto_trade_btn.clicked.connect(self.toggle_auto_trade)
        self.auto_trade_btn.setEnabled(False)
        layout.addWidget(self.auto_trade_btn)

        if _SCANNER_AVAILABLE:
            self.scan_btn = QPushButton("자동탐색 시작")
            self.scan_btn.setStyleSheet(
                "background-color: #FF9800; color: white; font-weight: bold; padding: 10px 20px;"
            )
            self.scan_btn.clicked.connect(self._toggle_scan)
            self.scan_btn.setEnabled(False)
            layout.addWidget(self.scan_btn)

        return frame

    def create_trading_tab(self):
        """매매 관리 탭"""
        widget = QWidget()
        layout = QHBoxLayout(widget)

        left_group = QGroupBox("보유 종목 현황")
        left_layout = QVBoxLayout(left_group)

        self.holdings_table = QTableWidget()
        self.holdings_table.setColumnCount(8)
        self.holdings_table.setHorizontalHeaderLabels([
            "종목코드", "종목명", "보유수량", "평균단가", "현재가", "평가금액", "손익", "수익률"
        ])
        self.holdings_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.holdings_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.holdings_table.itemSelectionChanged.connect(self.on_holding_selected)
        left_layout.addWidget(self.holdings_table)

        refresh_btn = QPushButton("잔고 새로고침")
        refresh_btn.clicked.connect(self.refresh_holdings)
        left_layout.addWidget(refresh_btn)

        layout.addWidget(left_group, 2)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        analysis_group = QGroupBox("종목 분석")
        analysis_layout = QGridLayout(analysis_group)

        self.analysis_code_label = QLabel("종목: -")
        self.analysis_ma20_label = QLabel("메인 기준: -")
        self.analysis_main_condition_label = QLabel("main condition: -")
        self.analysis_buy_signal_label = QLabel("매수 신호: -")
        self.analysis_position_label = QLabel("포지션: -")

        analysis_layout.addWidget(self.analysis_code_label, 0, 0, 1, 2)
        analysis_layout.addWidget(self.analysis_ma20_label, 1, 0)
        analysis_layout.addWidget(self.analysis_main_condition_label, 1, 1)
        analysis_layout.addWidget(self.analysis_buy_signal_label, 2, 0, 1, 2)
        analysis_layout.addWidget(self.analysis_position_label, 3, 0, 1, 2)

        right_layout.addWidget(analysis_group)

        # 수동 매도
        sell_group = QGroupBox("수동 매도")
        sell_layout = QGridLayout(sell_group)

        sell_layout.addWidget(QLabel("종목코드/종목명:"), 0, 0)
        self.manual_sell_code = QLineEdit()
        self.manual_sell_code.setPlaceholderText("예: 005930, 삼성전자")
        sell_layout.addWidget(self.manual_sell_code, 0, 1)

        sell_layout.addWidget(QLabel("수량:"), 1, 0)
        self.manual_sell_qty = QSpinBox()
        self.manual_sell_qty.setRange(1, 999999)
        self.manual_sell_qty.setValue(1)
        sell_layout.addWidget(self.manual_sell_qty, 1, 1)

        sell_layout.addWidget(QLabel("비중(%):"), 2, 0)
        self.manual_sell_ratio = QSpinBox()
        self.manual_sell_ratio.setRange(1, 100)
        self.manual_sell_ratio.setValue(100)
        self.manual_sell_ratio.setSuffix(" %")
        self.manual_sell_ratio.valueChanged.connect(self.on_sell_ratio_changed)
        sell_layout.addWidget(self.manual_sell_ratio, 2, 1)

        sell_layout.addWidget(QLabel("가격:"), 3, 0)
        self.manual_sell_price = QSpinBox()
        self.manual_sell_price.setRange(0, 99999999)
        self.manual_sell_price.setValue(0)
        self.manual_sell_price.setSpecialValueText("시장가")
        sell_layout.addWidget(self.manual_sell_price, 3, 1)

        self.manual_sell_btn = QPushButton("매도 주문 (수량)")
        self.manual_sell_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        self.manual_sell_btn.clicked.connect(self.do_manual_sell)
        self.manual_sell_btn.setEnabled(False)
        sell_layout.addWidget(self.manual_sell_btn, 4, 0)

        self.manual_sell_ratio_btn = QPushButton("매도 주문 (비중)")
        self.manual_sell_ratio_btn.setStyleSheet("background-color: #9C27B0; color: white; font-weight: bold;")
        self.manual_sell_ratio_btn.clicked.connect(self.do_manual_sell_by_ratio)
        self.manual_sell_ratio_btn.setEnabled(False)
        sell_layout.addWidget(self.manual_sell_ratio_btn, 4, 1)

        self.cancel_orders_btn = QPushButton("전량주문 취소")
        self.cancel_orders_btn.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold;")
        self.cancel_orders_btn.clicked.connect(self.do_cancel_all_orders)
        self.cancel_orders_btn.setEnabled(False)
        sell_layout.addWidget(self.cancel_orders_btn, 5, 0, 1, 2)

        right_layout.addWidget(sell_group)

        # 수동 매수
        buy_group = QGroupBox("수동 매수")
        buy_layout = QGridLayout(buy_group)

        buy_layout.addWidget(QLabel("종목코드/종목명:"), 0, 0)
        self.manual_buy_code = QLineEdit()
        self.manual_buy_code.setPlaceholderText("예: 005930, 삼성전자")
        buy_layout.addWidget(self.manual_buy_code, 0, 1)

        buy_layout.addWidget(QLabel("수량:"), 1, 0)
        self.manual_buy_qty = QSpinBox()
        self.manual_buy_qty.setRange(1, 999999)
        self.manual_buy_qty.setValue(1)
        buy_layout.addWidget(self.manual_buy_qty, 1, 1)

        buy_layout.addWidget(QLabel("가격:"), 2, 0)
        self.manual_buy_price = QSpinBox()
        self.manual_buy_price.setRange(0, 99999999)
        self.manual_buy_price.setValue(0)
        self.manual_buy_price.setSpecialValueText("시장가")
        buy_layout.addWidget(self.manual_buy_price, 2, 1)

        self.manual_buy_btn = QPushButton("매수 주문")
        self.manual_buy_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        self.manual_buy_btn.clicked.connect(self.do_manual_buy)
        self.manual_buy_btn.setEnabled(False)
        buy_layout.addWidget(self.manual_buy_btn, 3, 0, 1, 2)

        right_layout.addWidget(buy_group)

        # 매도 목표가
        target_group = QGroupBox("매도 목표가 (선택 종목)")
        target_layout = QVBoxLayout(target_group)

        self.sell_targets_table = QTableWidget()
        self.sell_targets_table.setColumnCount(3)
        self.sell_targets_table.setHorizontalHeaderLabels(["구분", "목표가", "상태"])
        self.sell_targets_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        target_layout.addWidget(self.sell_targets_table)

        right_layout.addWidget(target_group)

        right_layout.addStretch()
        layout.addWidget(right_widget, 1)

        return widget

    def create_watchlist_tab(self):
        """종목 관리 탭"""
        widget = QWidget()
        layout = QHBoxLayout(widget)

        left_group = QGroupBox("감시 종목 리스트 (자동매매 대상)")
        left_layout = QVBoxLayout(left_group)

        self.watchlist_table = QTableWidget()
        self.watchlist_table.setColumnCount(5)
        self.watchlist_table.setHorizontalHeaderLabels([
            "종목코드", "종목명", "현재가", "메인 기준", "main condition"
        ])
        self.watchlist_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.watchlist_table.setSelectionBehavior(QTableWidget.SelectRows)
        left_layout.addWidget(self.watchlist_table)

        add_layout = QHBoxLayout()
        self.add_code_input = QLineEdit()
        self.add_code_input.setPlaceholderText("종목코드 또는 종목명 입력 (예: 005930, 삼성전자)")
        add_layout.addWidget(self.add_code_input)

        add_btn = QPushButton("종목 추가")
        add_btn.clicked.connect(self.add_to_watchlist)
        self.add_code_input.returnPressed.connect(self.add_to_watchlist)
        add_layout.addWidget(add_btn)

        remove_btn = QPushButton("선택 삭제")
        remove_btn.clicked.connect(self.remove_from_watchlist)
        add_layout.addWidget(remove_btn)

        left_layout.addLayout(add_layout)

        refresh_watchlist_btn = QPushButton("종목 정보 새로고침")
        refresh_watchlist_btn.clicked.connect(self.refresh_watchlist)
        left_layout.addWidget(refresh_watchlist_btn)

        layout.addWidget(left_group)
        return widget

    def create_settings_tab(self):
        """설정 탭"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        buy_group = QGroupBox("매수 설정")
        buy_layout = QGridLayout(buy_group)

        _lbl_period = QLabel("main condition 기간:")
        self.setting_main_condition_period = QSpinBox()
        self.setting_main_condition_period.setRange(5, 60)
        self.setting_main_condition_period.setValue(self.config.get("buy", "main_condition_period"))
        buy_layout.addWidget(_lbl_period, 0, 0)
        buy_layout.addWidget(self.setting_main_condition_period, 0, 1)
        _lbl_period.hide()
        self.setting_main_condition_period.hide()

        _lbl_trigger = QLabel("트리거 % (하단):")
        self.setting_main_condition_percent = QSpinBox()
        self.setting_main_condition_percent.setRange(5, 50)
        self.setting_main_condition_percent.setValue(self.config.get("buy", "main_condition_percent") or 19)
        self.setting_main_condition_percent.setToolTip("매수 신호 트리거 조건 (예: 19% = MA 대비 -19%에서 트리거)")
        buy_layout.addWidget(_lbl_trigger, 0, 2)
        buy_layout.addWidget(self.setting_main_condition_percent, 0, 3)
        _lbl_trigger.hide()
        self.setting_main_condition_percent.hide()

        _lbl_buy_pct = QLabel("매수가 % (하단):")
        self.setting_main_condition_buy_percent = QSpinBox()
        self.setting_main_condition_buy_percent.setRange(5, 50)
        self.setting_main_condition_buy_percent.setValue(self.config.get("buy", "main_condition_buy_percent") or 20)
        self.setting_main_condition_buy_percent.setToolTip("실제 지정가 매수 주문 가격 (예: 20% = MA × 0.80 + 1호가)")
        buy_layout.addWidget(_lbl_buy_pct, 1, 0)
        buy_layout.addWidget(self.setting_main_condition_buy_percent, 1, 1)
        _lbl_buy_pct.hide()
        self.setting_main_condition_buy_percent.hide()

        _lbl_add_drop = QLabel("추가매수 하락률 %:")
        self.setting_add_drop = QSpinBox()
        self.setting_add_drop.setRange(5, 30)
        self.setting_add_drop.setValue(self.config.get("buy", "additional_buy_drop_percent"))
        buy_layout.addWidget(_lbl_add_drop, 1, 2)
        buy_layout.addWidget(self.setting_add_drop, 1, 3)
        _lbl_add_drop.hide()
        self.setting_add_drop.hide()

        buy_layout.addWidget(QLabel("1회 매수 금액:"), 2, 0)
        self.setting_buy_amount = QSpinBox()
        self.setting_buy_amount.setRange(100000, 100000000)
        self.setting_buy_amount.setSingleStep(100000)
        self.setting_buy_amount.setValue(self.config.get("buy", "buy_amount_per_stock"))
        self.setting_buy_amount.setSuffix(" 원")
        buy_layout.addWidget(self.setting_buy_amount, 2, 1)

        buy_layout.addWidget(QLabel("최대 동시 보유 종목수:"), 2, 2)
        self.setting_max_holding = QSpinBox()
        self.setting_max_holding.setRange(1, 50)
        self.setting_max_holding.setValue(self.config.get("buy", "max_holding_stocks") or 3)
        self.setting_max_holding.setSuffix(" 종목")
        buy_layout.addWidget(self.setting_max_holding, 2, 3)

        # 재진입 허용 체크박스 삭제됨 - 매도 발생 시 당일 재매수 금지

        layout.addWidget(buy_group)

        sell_group = QGroupBox("매도 설정")
        sell_layout = QGridLayout(sell_group)

        sell_layout.addWidget(QLabel("익절 1 (수익률 %):"), 0, 0)
        self.setting_profit1 = QDoubleSpinBox()
        self.setting_profit1.setRange(0.1, 50)
        self.setting_profit1.setDecimals(2)
        self.setting_profit1.setValue(self.config.get("sell", "profit_targets")[0])
        sell_layout.addWidget(self.setting_profit1, 0, 1)

        sell_layout.addWidget(QLabel("매도 비중 %:"), 0, 2)
        self.setting_ratio1 = QSpinBox()
        self.setting_ratio1.setRange(1, 100)
        self.setting_ratio1.setValue(self.config.get("sell", "profit_sell_ratios")[0])
        sell_layout.addWidget(self.setting_ratio1, 0, 3)

        sell_layout.addWidget(QLabel("익절 2 (수익률 %):"), 1, 0)
        self.setting_profit2 = QDoubleSpinBox()
        self.setting_profit2.setRange(0.1, 50)
        self.setting_profit2.setDecimals(2)
        self.setting_profit2.setValue(self.config.get("sell", "profit_targets")[1])
        sell_layout.addWidget(self.setting_profit2, 1, 1)

        sell_layout.addWidget(QLabel("매도 비중 %:"), 1, 2)
        self.setting_ratio2 = QSpinBox()
        self.setting_ratio2.setRange(1, 100)
        self.setting_ratio2.setValue(self.config.get("sell", "profit_sell_ratios")[1])
        sell_layout.addWidget(self.setting_ratio2, 1, 3)

        sell_layout.addWidget(QLabel("익절 3 (수익률 %):"), 2, 0)
        self.setting_profit3 = QDoubleSpinBox()
        self.setting_profit3.setRange(0.1, 50)
        self.setting_profit3.setDecimals(2)
        self.setting_profit3.setValue(self.config.get("sell", "profit_targets")[2])
        sell_layout.addWidget(self.setting_profit3, 2, 1)

        sell_layout.addWidget(QLabel("매도 비중 %:"), 2, 2)
        self.setting_ratio3 = QSpinBox()
        self.setting_ratio3.setRange(1, 100)
        self.setting_ratio3.setValue(self.config.get("sell", "profit_sell_ratios")[2])
        sell_layout.addWidget(self.setting_ratio3, 2, 3)

        sell_layout.addWidget(QLabel("메인 기준 도달시 매도 비중 %:"), 3, 0, 1, 2)
        self.setting_ma20_ratio = QSpinBox()
        self.setting_ma20_ratio.setRange(1, 100)
        self.setting_ma20_ratio.setValue(self.config.get("sell", "ma20_sell_ratio"))
        sell_layout.addWidget(self.setting_ma20_ratio, 3, 2, 1, 2)

        sell_group.hide()
        layout.addWidget(sell_group)

        # 모의투자 체크박스 삭제됨 - 로그인 시 서버 자동 감지

        save_btn = QPushButton("설정 저장")
        save_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)

        layout.addStretch()
        return widget

    def create_log_frame(self):
        """로그 프레임"""
        group = QGroupBox("로그")
        layout = QVBoxLayout(group)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        self.log_text.setFont(QFont("Consolas", 9))
        layout.addWidget(self.log_text)

        clear_btn = QPushButton("로그 지우기")
        clear_btn.clicked.connect(lambda: self.log_text.clear())
        layout.addWidget(clear_btn)

        return group

    def log(self, message):
        """로그 출력(버퍼링)"""
        try:
            self._log_buffer.append(str(message))
        except Exception:
            if hasattr(self, 'log_text') and self.log_text is not None:
                self.log_text.append(str(message))
                self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    
    def _flush_log_buffer(self):
        """로그 버퍼를 주기적으로 UI에 반영"""
        if not hasattr(self, "log_text") or self.log_text is None:
            return
        if not hasattr(self, "_log_buffer") or not self._log_buffer:
            return

        batch = 0
        while self._log_buffer and batch < 300:
            self.log_text.append(self._log_buffer.popleft())
            batch += 1

        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    def _drain_order_queue(self):
        """주문 큐를 메인(UI) 스레드에서 처리"""
        if self._is_stopping:
            return
        if not self.trader or not getattr(self.trader, "is_running", False):
            return
        # ✅ 주문은 TR 처리와 독립적으로 전송 가능
        try:
            self.trader.process_order_queue()
        except Exception as e:
            self.log(f"[시스템] 주문 큐 처리 오류: {e}")

    # =========================
    # 종목 캐시 로딩 (UI 프리징 방지)
    # =========================
    def _start_stock_cache_loading(self):
        """백그라운드에서 종목 캐시 로딩 시작"""
        if not self.kiwoom:
            return

        self.log("[시스템] 종목 캐시 로딩 시작...")
        self._cache_loader_worker = StockCacheLoaderWorker(self.kiwoom)
        self._cache_loader_worker.load_finished.connect(self._on_cache_load_finished)
        self._cache_loader_worker.start()

    def _on_cache_load_finished(self, success, count):
        """종목 캐시 로딩 완료 콜백"""
        if success:
            self.log(f"[시스템] 종목 캐시 로딩 완료: {count}개 종목")
        else:
            self.log("[시스템] 종목 캐시 로딩 실패 - 검색 시 API 호출 사용")

    # =========================
    # 로그인 / 계좌
    # =========================
    def do_login(self):
        """로그인"""
        try:
            self.log("[시스템] 키움증권 로그인 시도 중...")
            self.kiwoom = KiwoomAPI()

            if self.kiwoom.login():
                # ✅ 서버 구분 확인 (실서버/모의투자)
                server_gubun = self.kiwoom.get_server_gubun()
                is_real = self.kiwoom.is_real_server()

                self.log(f"[시스템] 로그인 성공! (서버: {server_gubun})")

                # ✅ 서버 구분에 따라 UI 색상 및 텍스트 변경
                if is_real:
                    self.status_label.setText(f"연결 상태: 연결됨 (실서버)")
                    self.status_label.setStyleSheet("color: green; font-weight: bold;")
                else:
                    self.status_label.setText(f"연결 상태: 연결됨 (모의투자)")
                    self.status_label.setStyleSheet("color: orange; font-weight: bold;")
                    # 모의투자 연결 시 경고 메시지
                    self.log("[경고] 모의투자 서버에 연결되었습니다!")
                    self.log("[안내] 실계좌 연결 방법:")
                    self.log("  1. 영웅문HTS 자동로그인을 해제하세요.")
                    self.log("  2. KOA Studio를 재실행하고 로그인 창에서 '모의투자' 체크 해제")
                    self.log("  3. 계좌 비밀번호를 KOA Studio에서 다시 등록하세요.")
                    QMessageBox.warning(
                        self,
                        "모의투자 서버 연결",
                        "현재 모의투자 서버에 연결되었습니다.\n\n"
                        "실계좌를 사용하려면:\n"
                        "1. 영웅문HTS 자동로그인을 해제\n"
                        "2. KOA Studio 재실행 후 로그인 시 '모의투자' 체크 해제\n"
                        "3. 계좌 비밀번호 다시 등록"
                    )

                self.login_btn.setEnabled(False)

                # ✅ 디버그 모드 활성화 (문제 해결 후 False로 변경)
                self.kiwoom.set_debug(True)

                # ✅ 계좌 데이터 시그널 연결
                self.kiwoom.account_signals.deposit_changed.connect(self._on_deposit_changed)
                self.kiwoom.account_signals.balance_changed.connect(self._on_balance_changed)
                self.kiwoom.account_signals.full_balance_updated.connect(self._on_full_balance_updated)
                self.kiwoom.account_signals.holdings_updated.connect(self._on_holdings_updated)

                # ✅ 실시간 시세 콜백 등록 (보유종목/감시종목 UI 실시간 갱신)
                self.kiwoom.set_real_data_callback(self._on_realtime_price_dispatch)

                # ✅ 종목 캐시 로드 (UI 프리징 방지 - 백그라운드 스레드에서 실행)
                self._start_stock_cache_loading()

                self.trader = AutoTrader(self.kiwoom, self.config)
                self.trader.set_log_callback(self.log)

                accounts = self.kiwoom.get_account_list() or []
                accounts = [a.strip() for a in accounts if a and a.strip()]

                self.account_combo.blockSignals(True)
                self.account_combo.clear()
                self.account_combo.addItems(accounts)
                self.account_combo.blockSignals(False)

                if not accounts:
                    self.log("[시스템] 계좌 목록이 비어있습니다. 자동매매를 사용할 수 없습니다.")
                    QMessageBox.warning(self, "계좌 없음", "계좌를 불러오지 못했습니다. (실/모의 설정 확인)")
                    self.auto_trade_btn.setEnabled(False)
                    return

                self.account_combo.setCurrentIndex(0)
                self.trader.set_account(accounts[0])
                self.log(f"[시스템] 계좌 설정: {accounts[0]}")

                self.auto_trade_btn.setEnabled(True)
                if hasattr(self, 'scan_btn'):
                    self.scan_btn.setEnabled(True)
                self.manual_sell_btn.setEnabled(True)
                self.manual_sell_ratio_btn.setEnabled(True)
                self.manual_buy_btn.setEnabled(True)
                self.cancel_orders_btn.setEnabled(True)

                self.refresh_timer.start(60000)
                self.refresh_data()
                self.refresh_watchlist(show_loading=True)  # 초기 감시 종목 표시

                self.trader.full_state_sync_on_startup()
                self._check_pending_orders_on_startup()

            else:
                self.log("[시스템] 로그인 실패!")
                QMessageBox.warning(self, "로그인 실패", "키움증권 로그인에 실패했습니다.")

        except Exception as e:
            self.log(f"[시스템] 로그인 오류: {e}")
            QMessageBox.critical(self, "오류", f"로그인 중 오류 발생: {e}")

    def on_account_changed(self, account):
        """계좌 변경"""
        if not account or not account.strip():
            self.auto_trade_btn.setEnabled(False)
            return

        if self.trader:
            self.trader.set_account(account.strip())
            self.auto_trade_btn.setEnabled(True)
            self.refresh_holdings()

    # =========================
    # 자동매매
    # =========================
    def toggle_auto_trade(self):
        """자동매매 시작/중지"""
        if not self.trader:
            return

        if not self.account_combo.currentText().strip():
            QMessageBox.warning(self, "오류", "유효한 계좌를 선택해주세요.")
            return

        # ✅ 정지 처리중이면 연타 방지
        if self._is_stopping:
            return

        if self.trader.is_running:
            # ✅ 1) 먼저 타이머를 멈춰 재진입/교착 가능성 최소화
            self._is_stopping = True
            self.trading_timer.stop()
            self.refresh_timer.stop()
            self.watchlist_refresh_timer.stop()
            # ✅ 주문 큐 타이머도 정지
            try:
                self.order_timer.stop()
            except Exception:
                pass

            # ✅ 2) 버튼을 즉시 바꿔서 UI 반응 확보
            self.auto_trade_btn.setEnabled(False)
            self.auto_trade_btn.setText("정지 처리중...")
            self.auto_trade_btn.setStyleSheet(
                "background-color: #9E9E9E; color: white; font-weight: bold; padding: 10px 20px;"
            )

            # ✅ 3) 실제 stop/save는 다음 이벤트 루프에서 실행 (UI 프리징 완화)
            QTimer.singleShot(0, self._stop_autotrade_async)
            return

        # 시작
        ok = False
        try:
            ok = self.trader.start()
        except Exception as e:
            self.log(f"[시스템] 자동매매 시작 오류: {e}")
            QMessageBox.critical(self, "오류", f"자동매매 시작 중 오류: {e}")
            return

        if ok:
            self.auto_trade_btn.setText("자동매매 중지")
            self.auto_trade_btn.setStyleSheet(
                "background-color: #f44336; color: white; font-weight: bold; padding: 10px 20px;"
            )

            # (권장) 시작 직후에도 stop을 눌렀을 때 대비해 플래그 리셋
            self._is_stopping = False

            # ✅ 블로킹 작업들을 비동기로 처리하여 UI 프리징 방지
            QTimer.singleShot(100, self._start_autotrade_async)

            # ✅ 주문 큐 타이머 시작 (주문은 메인 스레드에서만)
            try:
                self.order_timer.start(20)
            except Exception:
                pass

            self.trading_timer.start(20000)
            self.refresh_timer.start(60000)  # 잔고 갱신 60초
            self.watchlist_refresh_timer.start(600000)  # 감시 종목 갱신 10분
        else:
            self.log("[시스템] 자동매매 시작 실패 (AutoTrader.start()가 False 반환)")
            QMessageBox.warning(self, "시작 실패", "자동매매 시작에 실패했습니다. 로그를 확인해주세요.")

    def _start_autotrade_async(self):
        """자동매매 시작 후 블로킹 작업을 비동기로 처리"""
        if self._is_stopping or not self.trader or not self.trader.is_running:
            return

        # TR 처리 중이면 복원 지연 후 재시도
        if self.kiwoom and self.kiwoom.is_tr_queue_busy():
            if not self._restore_retry_scheduled:
                self._restore_retry_scheduled = True
                QTimer.singleShot(1500, self._restore_orders_async)
            return

        try:
            self.trader.clear_stale_pending_orders()
        except Exception as e:
            self.log(f"[시스템] 미체결 주문 정리 오류: {e}")

        # 주문 복원은 별도 타이머로 처리 (UI 프리징 방지)
        # 자동매매 시작 직후 1~2초 지연 후 복원
        QTimer.singleShot(1500, self._restore_orders_async)

    def _restore_orders_async(self):
        """주문 복원을 비동기로 처리"""
        if self._is_stopping or not self.trader or not self.trader.is_running:
            return

        # ✅ 거래 가능 시간에만 복원 실행 (정규장 또는 NXT 프리/애프터)
        if not self.trader.is_any_trading_time():
            self.log("[시스템] 거래 가능 시간이 아니어서 주문 복원 대기 - 장 열림 시 자동 복원됨")
            return

        try:
            self._restore_retry_scheduled = False
            self.trader.check_and_restore_orders()
            self._orders_restored_today = True  # ✅ 복원 완료 표시
        except Exception as e:
            self.log(f"[시스템] 주문 복원 오류: {e}")

    def _check_market_open_and_restore(self):
        """
        장 열림 감지 시 check_and_restore_orders() 자동 호출
        - 매 1분마다 체크
        - 날짜 변경 시 플래그 초기화
        - 장이 열렸고 아직 복원하지 않았으면 주문 복원 실행
        """
        from datetime import datetime, time as dt_time

        now = datetime.now()
        today = now.date()

        # 날짜가 변경되면 플래그 초기화
        if self._last_market_open_check_date != today:
            self._last_market_open_check_date = today
            self._orders_restored_today = False

        # trader가 없거나 실행 중이 아니면 스킵
        if not self.trader or not self.trader.is_running:
            return

        # 거래 가능 시간(정규장 또는 NXT 프리/애프터) 체크
        if not self.trader.is_any_trading_time():
            return

        # ✅ TR 재진입 방지: TR 또는 TR 큐 처리 중이면 스킵
        if self.kiwoom and self.kiwoom.is_tr_queue_busy():
            if not self._restore_retry_scheduled:
                self._restore_retry_scheduled = True
                QTimer.singleShot(1500, self._restore_orders_async)
            return

        # ✅ 이미 복원했어도 미체결 주문이 없으면 다시 복원 시도
        if self._orders_restored_today:
            try:
                # 실제 미체결 주문 확인
                api_pending = self.trader.kiwoom.get_open_orders(self.trader.account)
                pending_orders = self.trader.config.get_pending_orders()

                if api_pending or not pending_orders:
                    # 미체결 주문이 있거나 복원할 주문이 없으면 스킵
                    return
                else:
                    # 미체결 주문이 없고 복원할 주문이 있으면 다시 복원
                    self.log("[시스템] 기존 주문 취소 감지 - 주문 재복원 시작")
                    self._orders_restored_today = False
            except Exception as e:
                self.log(f"[시스템] 미체결 주문 확인 오류: {e}")
                return

        # 주문 복원 실행
        market_type = self.trader.get_current_market_type()
        self.log(f"[시스템] 거래 가능 시간({market_type}) - 주문 복원 자동 실행")
        try:
            self._restore_retry_scheduled = False
            self.trader.check_and_restore_orders()
            self._orders_restored_today = True
        except Exception as e:
            self.log(f"[시스템] 장 열림 주문 복원 오류: {e}")

    def _stop_autotrade_async(self):
        """UI 프리징을 줄이기 위해 stop/save를 이벤트루프 다음 tick에서 수행"""
        t0 = time.time()
        try:
            self.log("[시스템] 자동매매 정지 시작...")

            # ✅ stop이 오래 걸릴 수 있으니, 먼저 running 플래그를 내려서 루프가 빨리 멈추게 유도
            # (가능하면 AutoTrader.stop() 내부에서 처리하는 게 더 좋음)
            try:
                self.trader.is_running = False
            except Exception:
                pass

            self.trader.stop()
            self.log(f"[DBG] trader.stop() 완료 ({time.time() - t0:.2f}s)")

            t1 = time.time()
            self.trader.save_current_state()
            self.log(f"[DBG] save_current_state() 완료 ({time.time() - t1:.2f}s)")

            self.log("[시스템] 자동매매 중지 완료")
        except Exception as e:
            self.log(f"[시스템] 자동매매 정지 오류: {e}")
        finally:
            self._is_stopping = False

            # UI 복구
            self.auto_trade_btn.setEnabled(True)
            self.auto_trade_btn.setText("자동매매 시작")
            self.auto_trade_btn.setStyleSheet(
                "background-color: #4CAF50; color: white; font-weight: bold; padding: 10px 20px;"
            )

            # (선택) 정지 후에는 잔고/워치리스트는 계속 갱신되게
            if self.kiwoom and self.kiwoom.is_connected():
                self.refresh_timer.start(60000)

    def check_trading_signals(self):
        """
        매매 신호 확인 (순환 조회용)
        - 실시간 등록 종목: 이벤트 엔진에서 자동 처리
        - 실시간 미등록 종목: 이 타이머로 순환 조회
        """
        if self._is_stopping:
            return

        if not self.trader or not self.trader.is_running:
            return

        if self._is_checking_signals:
            return

        # ✅ TR 재진입 방지: TR 또는 TR 큐 처리 중이면 스킵 (다음 타이머 주기에 재시도)
        if self.kiwoom and self.kiwoom.is_tr_queue_busy():
            return

        self._is_checking_signals = True

        try:
            if self.trader.event_engine:
                watchlist = self.config.get_watchlist()
                watchlist_codes = [item["code"] for item in watchlist]
                unregistered = self.trader.event_engine.realtime_manager.get_unregistered_stocks(watchlist_codes)

                for code in unregistered[:5]:
                    if self._is_stopping or not self.trader.is_running:
                        break
                    self.trader.check_and_trade(code)
            else:
                watchlist = self.config.get_watchlist()
                for stock in watchlist:
                    if self._is_stopping or not self.trader.is_running:
                        break
                    self.trader.check_and_trade(stock["code"])
        finally:
            self._is_checking_signals = False

    # =========================
    # 계좌 데이터 시그널 슬롯
    # =========================
    def _on_deposit_changed(self, deposit):
        """예수금 변경 시그널 처리"""
        try:
            self.balance_label.setText(f"예수금: {deposit:,}원")
        except Exception:
            pass
        if self.trader:
            self.trader.update_available_funds(deposit)

    def _on_balance_changed(self, _code, _quantity, _avg_price):
        """잔고 변경 시그널 처리 (개별 종목) - 디바운스 적용으로 과도한 TR 호출 방지"""
        try:
            # ✅ 1초 디바운스: 연속 체결 시 마지막 이벤트 후 1초 뒤에 한 번만 TR 조회
            self._balance_changed_timer.start(1000)
        except Exception:
            pass

    def _on_full_balance_updated(self, balance):
        """전체 잔고 정보 갱신 시그널 처리"""
        try:
            deposit = balance.get("deposit", 0) or 0
            if deposit > 0:
                self.balance_label.setText(f"예수금: {deposit:,}원")
        except Exception:
            pass

    def _on_holdings_updated(self, holdings):
        """보유종목 전체 갱신 시그널 처리"""
        try:
            self.holdings_table.setRowCount(len(holdings))
            self._holdings_code_to_row = {}

            for row, holding in enumerate(holdings):
                code = holding["code"]
                self._holdings_code_to_row[code] = row
                self.holdings_table.setItem(row, 0, QTableWidgetItem(code))
                self.holdings_table.setItem(row, 1, QTableWidgetItem(holding["name"]))
                self.holdings_table.setItem(row, 2, QTableWidgetItem(f"{holding['quantity']:,}"))
                self.holdings_table.setItem(row, 3, QTableWidgetItem(f"{holding['avg_price']:,}"))
                self.holdings_table.setItem(row, 4, QTableWidgetItem(f"{holding['current_price']:,}"))
                self.holdings_table.setItem(row, 5, QTableWidgetItem(f"{holding['eval_amount']:,}"))
                self.holdings_table.setItem(row, 6, QTableWidgetItem(f"{holding['profit']:,}"))

                profit_rate = holding.get("profit_rate", 0.0) or 0.0
                rate_item = QTableWidgetItem(f"{profit_rate:.2f}%")
                if profit_rate > 0:
                    rate_item.setForeground(QColor("red"))
                elif profit_rate < 0:
                    rate_item.setForeground(QColor("blue"))
                self.holdings_table.setItem(row, 7, rate_item)
        except Exception:
            pass

    # =========================
    # 실시간 시세 UI 반영
    # =========================
    def _on_realtime_price_dispatch(self, code, price, volume):
        """
        실시간 시세 수신 통합 디스패치:
        - UI 갱신
        - (event_engine가 kiwoom에 연결되지 않은 경우) AutoTrader 트리거로 전달
        """
        try:
            self._on_realtime_price(code, price, volume)
        except Exception:
            pass

        # event_engine가 직접 kiwoom에 연결되어 있지 않다면 동일 스트림을 전달
        try:
            if (self.trader and self.trader.event_engine and
                    self.kiwoom and self.kiwoom.event_engine is None):
                self.trader.event_engine.push_event(
                    "price", code, {"price": price, "volume": volume}
                )
        except Exception:
            pass

    def _on_realtime_price(self, code, price, volume):
        """실시간 시세 콜백 → 보유종목/감시종목 테이블 즉시 갱신"""
        try:
            self._update_holdings_realtime(code, price)
        except Exception:
            pass
        try:
            self._update_watchlist_realtime(code, price)
        except Exception:
            pass

    def _update_holdings_realtime(self, code, price):
        """보유종목 테이블에서 해당 종목의 현재가·평가금액·손익·수익률 실시간 갱신"""
        row = self._holdings_code_to_row.get(code)
        if row is None or row >= self.holdings_table.rowCount():
            return

        # 보유수량·평균단가는 테이블에서 읽기
        qty_item = self.holdings_table.item(row, 2)
        avg_item = self.holdings_table.item(row, 3)
        if not qty_item or not avg_item:
            return

        try:
            quantity = int(qty_item.text().replace(",", ""))
            avg_price = int(avg_item.text().replace(",", ""))
        except (ValueError, AttributeError):
            return

        if quantity <= 0 or avg_price <= 0:
            return

        eval_amount = price * quantity
        profit = eval_amount - (avg_price * quantity)
        profit_rate = ((price - avg_price) / avg_price) * 100

        self.holdings_table.setItem(row, 4, QTableWidgetItem(f"{price:,}"))
        self.holdings_table.setItem(row, 5, QTableWidgetItem(f"{eval_amount:,}"))
        self.holdings_table.setItem(row, 6, QTableWidgetItem(f"{profit:,}"))

        rate_item = QTableWidgetItem(f"{profit_rate:.2f}%")
        if profit_rate > 0:
            rate_item.setForeground(QColor("red"))
        elif profit_rate < 0:
            rate_item.setForeground(QColor("blue"))
        self.holdings_table.setItem(row, 7, rate_item)

    def _update_watchlist_realtime(self, code, price):
        """감시종목 테이블에서 해당 종목의 현재가 실시간 갱신"""
        row = self._watchlist_code_to_row.get(code)
        if row is None or row >= self.watchlist_table.rowCount():
            # 매핑이 없으면 테이블을 스캔해 보정
            for r in range(self.watchlist_table.rowCount()):
                item = self.watchlist_table.item(r, 0)
                if item and item.text() == code:
                    row = r
                    self._watchlist_code_to_row[code] = r
                    break
            if row is None or row >= self.watchlist_table.rowCount():
                return
        self.watchlist_table.setItem(row, 2, QTableWidgetItem(f"{price:,}"))

    # =========================
    # 데이터 갱신
    # =========================
    def refresh_data(self):
        """잔고 갱신 (TR 큐 기반, 60초 주기)"""
        if self._is_stopping:
            return
        # ✅ 잔고만 갱신 (감시 종목은 별도 타이머로 10분 주기)
        self.refresh_holdings()

    def refresh_holdings(self):
        """보유 종목 갱신 (큐 기반 비동기)"""
        if not self.kiwoom or not self.kiwoom.is_connected():
            return

        account = self.account_combo.currentText().strip()
        if not account:
            return

        if self._holdings_refresh_inflight:
            return

        # ✅ TR 큐에 잔고 조회 요청 추가 (중첩 호출 방지)
        self._holdings_refresh_inflight = True
        self.log(f"[잔고조회] 계좌번호: {account} (큐 기반 요청)")
        self.kiwoom.get_balance_async(account, self._on_balance_received)

    def _on_balance_received(self, balance):
        """잔고 조회 결과 콜백 (큐에서 호출)"""
        if balance is None:
            self._holdings_refresh_inflight = False
            self.log("[잔고조회] 조회 실패")
            return

        try:
            account = self.account_combo.currentText().strip()
            deposit = balance.get("deposit", 0) or 0
            holdings = balance.get("holdings", [])
            total_eval = balance.get("total_eval", 0) or 0
            self.log(f"[잔고조회] 예수금={deposit:,}원, 총평가={total_eval:,}원, 보유종목={len(holdings)}개")

            # ✅ 예수금이 0이면 opw00001 TR로 재조회 시도 (큐 기반)
            if deposit == 0 and account:
                self.log(f"[잔고조회] opw00018 예수금=0, opw00001로 재조회 요청...")
                self.kiwoom.get_deposit_async(account, self._on_deposit_received)
            else:
                if self.trader:
                    self.trader.update_available_funds(deposit)
                self._update_holdings_ui(balance, deposit)
                self._holdings_refresh_inflight = False

        except Exception as e:
            self._holdings_refresh_inflight = False
            self.log(f"[시스템] 잔고 조회 결과 처리 오류: {e}")

    def _on_deposit_received(self, deposit_info):
        """예수금 재조회 결과 콜백"""
        if deposit_info is None:
            self._holdings_refresh_inflight = False
            self.log("[잔고조회] 예수금 재조회 실패")
            return

        try:
            self.log(f"[잔고조회] opw00001 결과: {deposit_info}")
            # 주문가능금액 > D+2예수금 > 예수금 순으로 사용
            deposit = deposit_info.get("order_available", 0) or 0
            if deposit == 0:
                deposit = deposit_info.get("deposit_d2", 0) or 0
            if deposit == 0:
                deposit = deposit_info.get("deposit", 0) or 0

            # ✅ 예수금이 여전히 0이면 원인 안내
            if deposit == 0 and self.kiwoom.is_real_server():
                self.log("[경고] 실계좌 예수금 조회 실패!")
                self.log("[안내] 해결 방법:")
                self.log("  1. KOA Studio에서 [도구 > 계좌비밀번호 저장] 확인")
                self.log("  2. 계좌번호 선택 후 비밀번호 입력 및 '등록' 클릭")
                self.log("  3. 'AUTO' 체크박스가 선택되어 있는지 확인")
                self.log("  4. 프로그램 재시작 후 다시 시도")

            self.balance_label.setText(f"예수금: {deposit:,}원")
            if self.trader:
                self.trader.update_available_funds(deposit)

        except Exception as e:
            self.log(f"[잔고조회] 예수금 처리 오류: {e}")
        finally:
            self._holdings_refresh_inflight = False

    def _update_holdings_ui(self, balance, deposit):
        """보유종목 UI 업데이트"""
        try:
            self.balance_label.setText(f"예수금: {deposit:,}원")

            holdings = balance.get("holdings", [])
            self.holdings_table.setRowCount(len(holdings))
            self._holdings_code_to_row = {}

            for row, holding in enumerate(holdings):
                code = holding["code"]
                self._holdings_code_to_row[code] = row
                self.holdings_table.setItem(row, 0, QTableWidgetItem(code))
                self.holdings_table.setItem(row, 1, QTableWidgetItem(holding["name"]))
                self.holdings_table.setItem(row, 2, QTableWidgetItem(f"{holding['quantity']:,}"))
                self.holdings_table.setItem(row, 3, QTableWidgetItem(f"{holding['avg_price']:,}"))
                self.holdings_table.setItem(row, 4, QTableWidgetItem(f"{holding['current_price']:,}"))
                self.holdings_table.setItem(row, 5, QTableWidgetItem(f"{holding['eval_amount']:,}"))
                self.holdings_table.setItem(row, 6, QTableWidgetItem(f"{holding['profit']:,}"))

                profit_rate = holding.get("profit_rate", 0.0) or 0.0
                rate_item = QTableWidgetItem(f"{profit_rate:.2f}%")
                if profit_rate > 0:
                    rate_item.setForeground(QColor("red"))
                elif profit_rate < 0:
                    rate_item.setForeground(QColor("blue"))
                self.holdings_table.setItem(row, 7, rate_item)

            if self.trader:
                self.trader.sync_positions_from_account(balance)

        except Exception as e:
            self.log(f"[시스템] 보유종목 UI 업데이트 오류: {e}")

    def refresh_watchlist(self, show_loading=False):
        """감시 종목 갱신 (비동기 방식으로 UI 프리징 방지)"""
        if self._is_stopping:
            return

        if self._is_refreshing_watchlist:
            return
        self._is_refreshing_watchlist = True
        self._watchlist_refresh_generation += 1
        generation = self._watchlist_refresh_generation
        self._watchlist_refresh_pending_codes.clear()

        try:
            watchlist = self.config.get_watchlist()

            now = time.time()
            if now - self._last_watchlist_log_ts > 10:
                self.log(f"[시스템] 감시 종목 로드: {len(watchlist)}개")
                self._last_watchlist_log_ts = now

            self._update_watchlist_header()

            # ✅ 행 수가 다를 때만 setRowCount 호출 (불필요한 리셋 방지)
            current_row_count = self.watchlist_table.rowCount()
            self.watchlist_table.setUpdatesEnabled(False)
            try:
                if current_row_count != len(watchlist):
                    self.watchlist_table.setRowCount(len(watchlist))

                period = self.config.get("buy", "main_condition_period") or 20
                percent = self.config.get("buy", "main_condition_percent") or 19

                # ✅ 코드/이름 매핑 갱신 + 기본 정보 설정 (기존 값 유지)
                self._watchlist_code_to_row = {}
                for row, stock in enumerate(watchlist):
                    code = stock["code"]
                    name = stock.get("name", "")
                    self._watchlist_code_to_row[code] = row

                    # 코드/이름은 항상 설정 (변경될 수 있음)
                    self.watchlist_table.setItem(row, 0, QTableWidgetItem(code))
                    self.watchlist_table.setItem(row, 1, QTableWidgetItem(name))

                    # ✅ 기존 값이 없을 때만 "-"로 초기화 (기존 값 유지)
                    if not self.watchlist_table.item(row, 2):
                        self.watchlist_table.setItem(row, 2, QTableWidgetItem("-"))
                    if not self.watchlist_table.item(row, 3):
                        self.watchlist_table.setItem(row, 3, QTableWidgetItem("-"))
                    if not self.watchlist_table.item(row, 4):
                        self.watchlist_table.setItem(row, 4, QTableWidgetItem("-"))

                # 캐시된 데이터로 먼저 표시 (이벤트 엔진의 배치 스케줄러 캐시 사용)
                if self.trader and self.trader.event_engine:
                    batch_scheduler = self.trader.event_engine.batch_scheduler
                    for row, stock in enumerate(watchlist):
                        code = stock["code"]
                        cached_candles = batch_scheduler.get_cached_candles(code)
                        if cached_candles:
                            try:
                                current_price = cached_candles[0].get("close")
                                main_condition = self.ta.get_main_condition_levels(cached_candles, period, percent)
                                self.watchlist_table.setItem(row, 2, QTableWidgetItem(self._fmt_int_or_dash(current_price)))
                                self.watchlist_table.setItem(row, 3, QTableWidgetItem(self._fmt_int_or_dash(main_condition.get("ma"))))
                                self.watchlist_table.setItem(row, 4, QTableWidgetItem(self._fmt_int_or_dash(main_condition.get("lower"))))
                            except Exception as e:
                                self.log(f"[시스템] 감시 종목 지표 갱신 실패: {code} ({e})")
            finally:
                self.watchlist_table.setUpdatesEnabled(True)

            self.watchlist_table.viewport().update()

            # 캐시가 없는 종목들만 비동기로 조회 시작 (UI 프리징 방지)
            self._watchlist_refresh_queue = []
            for row, stock in enumerate(watchlist):
                code = stock["code"]
                has_cache = False
                if self.trader and self.trader.event_engine:
                    has_cache = self.trader.event_engine.batch_scheduler.is_cache_valid(code)
                if not has_cache:
                    self._watchlist_refresh_queue.append(
                        {"generation": generation, "row": row, "code": code}
                    )
                    self._watchlist_refresh_pending_codes.add(code)

            self._watchlist_refresh_period = period
            self._watchlist_refresh_percent = percent

            # 큐가 있으면 비동기 갱신 시작
            if self._watchlist_refresh_queue and self.kiwoom and self.kiwoom.is_connected():
                self._watchlist_refresh_total = len(self._watchlist_refresh_queue)
                self._watchlist_refresh_done = 0
                self.log(f"[시스템] 종목 정보 조회 시작: {self._watchlist_refresh_total}개 종목")
                if show_loading:
                    self._show_watchlist_loading_dialog()
                QTimer.singleShot(100, lambda g=generation: self._refresh_watchlist_next(g))
            else:
                self._is_refreshing_watchlist = False
                if not self.kiwoom or not self.kiwoom.is_connected():
                    self.log("[시스템] 로그인 후 종목 정보를 새로고침해주세요.")

        except Exception as e:
            self.log(f"[시스템] 감시 종목 갱신 오류: {e}")
            self._is_refreshing_watchlist = False

        self._schedule_watchlist_realtime_registration()

    def _refresh_watchlist_for_codes(self, codes, show_loading=False):
        """선택 종목만 부분 갱신 (일봉 TR은 필요한 종목만 큐에 추가)"""
        if self._is_stopping:
            return

        if not codes:
            return

        period = self.config.get("buy", "main_condition_period") or 20
        percent = self.config.get("buy", "main_condition_percent") or 19

        to_queue = []
        generation = self._watchlist_refresh_generation

        # 캐시가 있으면 즉시 반영, 없으면 TR 큐에 추가
        self.watchlist_table.setUpdatesEnabled(False)
        try:
            for code in codes:
                row = self._watchlist_code_to_row.get(code)
                if row is None:
                    continue

                has_cache = False
                if self.trader and self.trader.event_engine:
                    batch_scheduler = self.trader.event_engine.batch_scheduler
                    cached_candles = batch_scheduler.get_cached_candles(code)
                    if cached_candles:
                        try:
                            current_price = cached_candles[0].get("close")
                            main_condition = self.ta.get_main_condition_levels(
                                cached_candles, period, percent
                            )
                            self.watchlist_table.setItem(
                                row, 2, QTableWidgetItem(self._fmt_int_or_dash(current_price))
                            )
                            self.watchlist_table.setItem(
                                row, 3, QTableWidgetItem(self._fmt_int_or_dash(main_condition.get("ma")))
                            )
                            self.watchlist_table.setItem(
                                row, 4, QTableWidgetItem(self._fmt_int_or_dash(main_condition.get("lower")))
                            )
                            has_cache = True
                        except Exception as e:
                            self.log(f"[시스템] 감시 종목 캐시 갱신 실패: {code} ({e})")
                    else:
                        has_cache = batch_scheduler.is_cache_valid(code)

                if not has_cache:
                    if code not in self._watchlist_refresh_pending_codes:
                        to_queue.append({"generation": generation, "row": row, "code": code})
                        self._watchlist_refresh_pending_codes.add(code)
        finally:
            self.watchlist_table.setUpdatesEnabled(True)

        if not to_queue:
            return

        self._watchlist_refresh_period = period
        self._watchlist_refresh_percent = percent

        if not self._is_refreshing_watchlist:
            self._watchlist_refresh_generation += 1
            generation = self._watchlist_refresh_generation
            self._watchlist_refresh_pending_codes.clear()
            for entry in to_queue:
                entry["generation"] = generation
                self._watchlist_refresh_pending_codes.add(entry["code"])
            self._watchlist_refresh_queue = to_queue
            self._watchlist_refresh_total = len(to_queue)
            self._watchlist_refresh_done = 0
            self._is_refreshing_watchlist = True

            if self.kiwoom and self.kiwoom.is_connected():
                if show_loading:
                    self._show_watchlist_loading_dialog()
                QTimer.singleShot(100, lambda g=generation: self._refresh_watchlist_next(g))
            else:
                self._is_refreshing_watchlist = False
        else:
            self._watchlist_refresh_queue.extend(to_queue)
            self._watchlist_refresh_total += len(to_queue)

    def _refresh_watchlist_next(self, generation=None):
        """비동기로 감시 종목 정보를 하나씩 갱신 (TR 큐 기반)"""
        if self._is_stopping:
            self._is_refreshing_watchlist = False
            return

        if generation is not None and generation != self._watchlist_refresh_generation:
            return

        if not self._watchlist_refresh_queue:
            self._is_refreshing_watchlist = False
            self.watchlist_table.viewport().update()
            return

        if not self.kiwoom or not self.kiwoom.is_connected():
            self._is_refreshing_watchlist = False
            return

        entry = self._watchlist_refresh_queue.pop(0)
        row = entry["row"]
        code = entry["code"]
        entry_generation = entry["generation"]

        if entry_generation != self._watchlist_refresh_generation:
            if self._watchlist_refresh_queue:
                QTimer.singleShot(0, lambda g=self._watchlist_refresh_generation: self._refresh_watchlist_next(g))
            else:
                self._is_refreshing_watchlist = False
            return

        # 테이블 행 유효성 확인
        if row >= self.watchlist_table.rowCount():
            # 테이블이 리셋되었을 수 있음, 다음 종목으로 진행
            if self._watchlist_refresh_queue:
                QTimer.singleShot(100, lambda g=entry_generation: self._refresh_watchlist_next(g))
            else:
                self._is_refreshing_watchlist = False
            return

        # ✅ TR 큐에 일봉 조회 요청 추가 (row, code를 클로저로 캡처)
        def on_candles_received(candles, g=entry_generation, r=row, c=code):
            self._on_watchlist_candles_received(g, r, c, candles)

        count = max(self._watchlist_refresh_period + 5, 25)
        self.kiwoom.get_daily_candles_async(code, on_candles_received, count)

    def _on_watchlist_candles_received(self, generation, row, code, candles):
        """감시종목 일봉 조회 결과 콜백"""
        try:
            if generation != self._watchlist_refresh_generation:
                return

            # 테이블 행 유효성 재확인
            if row >= self.watchlist_table.rowCount():
                self._continue_watchlist_refresh(generation, code)
                return

            if candles and len(candles) > 0:
                current_price = candles[0].get("close", 0)
                main_condition = self.ta.get_main_condition_levels(candles, self._watchlist_refresh_period, self._watchlist_refresh_percent)

                # UI 업데이트
                self.watchlist_table.setItem(row, 2, QTableWidgetItem(self._fmt_int_or_dash(current_price)))
                self.watchlist_table.setItem(row, 3, QTableWidgetItem(self._fmt_int_or_dash(main_condition.get("ma"))))
                self.watchlist_table.setItem(row, 4, QTableWidgetItem(self._fmt_int_or_dash(main_condition.get("lower"))))

                # 캐시 업데이트 (이벤트 엔진이 있으면)
                if self.trader and self.trader.event_engine:
                    self.trader.event_engine.batch_scheduler.update_cache(code, candles)

                self._continue_watchlist_refresh(generation, code)
            else:
                # 일봉 데이터 실패 시 현재가만이라도 조회 (opt10001 fallback - 큐 기반)
                self.log(f"[시스템] [{code}] 일봉 데이터 없음, 현재가 조회 시도...")

                def on_stock_info_received(stock_info, g=generation, r=row, c=code):
                    self._on_watchlist_stock_info_received(g, r, c, stock_info)

                self.kiwoom.get_stock_info_async(code, on_stock_info_received)

        except Exception as e:
            self.log(f"[시스템] [{code}] 일봉 처리 오류: {e}")
            self._continue_watchlist_refresh(generation, code)

    def _on_watchlist_stock_info_received(self, generation, row, code, stock_info):
        """감시종목 현재가 조회 결과 콜백 (fallback)"""
        try:
            if generation != self._watchlist_refresh_generation:
                return

            if row >= self.watchlist_table.rowCount():
                self._continue_watchlist_refresh(generation, code)
                return

            if stock_info and stock_info.get("price", 0) > 0:
                current_price = stock_info.get("price", 0)
                self.watchlist_table.setItem(row, 2, QTableWidgetItem(self._fmt_int_or_dash(current_price)))
                self.watchlist_table.setItem(row, 3, QTableWidgetItem("-"))
                self.watchlist_table.setItem(row, 4, QTableWidgetItem("-"))
                self.log(f"[시스템] [{code}] 현재가 조회 성공: {current_price:,}원")
            else:
                self.log(f"[시스템] [{code}] 현재가 조회 실패")

        except Exception as e:
            self.log(f"[시스템] [{code}] 현재가 처리 오류: {e}")

        self._continue_watchlist_refresh(generation, code)

    def _continue_watchlist_refresh(self, generation, code=None):
        """감시종목 갱신 계속 진행"""
        if generation != self._watchlist_refresh_generation:
            return

        if code:
            self._watchlist_refresh_pending_codes.discard(code)
        self._watchlist_refresh_done += 1

        # 진행률 업데이트
        if self._watchlist_loading_dialog and self._watchlist_refresh_total > 0:
            self._watchlist_loading_dialog.update_progress(
                self._watchlist_refresh_done, self._watchlist_refresh_total
            )

        # 85% 이상 불러왔으면 알림창 닫기
        if self._watchlist_refresh_total > 0:
            progress = self._watchlist_refresh_done / self._watchlist_refresh_total * 100
            if progress >= 85:
                self._hide_watchlist_loading_dialog()

        if self._watchlist_refresh_queue:
            # 다음 종목은 TR 큐가 알아서 순차 처리하므로 바로 호출
            QTimer.singleShot(50, lambda g=generation: self._refresh_watchlist_next(g))
        else:
            self._hide_watchlist_loading_dialog()
            self._is_refreshing_watchlist = False
            self.watchlist_table.viewport().update()

    def _show_watchlist_loading_dialog(self):
        """감시 종목 로딩 알림창 표시"""
        if self._watchlist_loading_dialog is None:
            self._watchlist_loading_dialog = WatchlistLoadingDialog(self)
        self._watchlist_loading_dialog.show()

    def _hide_watchlist_loading_dialog(self):
        """감시 종목 로딩 알림창 닫기"""
        if self._watchlist_loading_dialog:
            self._watchlist_loading_dialog.hide()

    # =========================
    # 워치리스트 관리
    # =========================
    def _unregister_watchlist_realtime(self):
        """감시종목 실시간 등록 해제"""
        if not self.kiwoom:
            return
        for screen_no in self._watchlist_rt_screens:
            try:
                self.kiwoom.set_real_remove(screen_no, "ALL")
            except Exception:
                pass
        self._watchlist_rt_registered = False

    def _register_watchlist_realtime(self):
        """감시종목 실시간 등록 (200개 이하일 때만 전부 등록)"""
        if not self.kiwoom or not self.kiwoom.is_connected():
            return

        watchlist = self.config.get_watchlist()
        codes = [item.get("code", "").strip() for item in watchlist if item.get("code")]
        codes = [c for c in codes if c]

        if len(codes) > 200:
            # 제한 초과 시 실시간 등록 유지하지 않음
            self._unregister_watchlist_realtime()
            return

        # 기존 등록 해제 후 재등록
        self._unregister_watchlist_realtime()

        # 화면번호당 최대 100종목씩 등록
        chunks = [codes[i:i + 100] for i in range(0, len(codes), 100)]
        for idx, screen_no in enumerate(self._watchlist_rt_screens):
            if idx >= len(chunks):
                break
            codes_str = ";".join(chunks[idx])
            try:
                self.kiwoom.set_real_reg(screen_no, codes_str, "10;15;20", "0")
            except Exception:
                pass

        self._watchlist_rt_registered = True

    def _refresh_watchlist_realtime_registration(self):
        """감시종목 실시간 등록 상태 갱신"""
        self._schedule_watchlist_realtime_registration()

    def add_to_watchlist(self):
        """감시 종목 추가 (종목코드 또는 종목명으로 검색)"""
        input_text = self.add_code_input.text().strip()
        if not input_text:
            QMessageBox.warning(self, "입력 오류", "종목코드 또는 종목명을 입력해주세요.")
            return

        code = ""
        name = ""

        # 6자리 숫자인 경우 종목코드로 처리
        if input_text.isdigit() and len(input_text) == 6:
            code = input_text
            if self.kiwoom and self.kiwoom.is_connected():
                # ✅ 캐시에서 먼저 조회 (빠름)
                name = self.kiwoom.get_stock_name_from_cache(code)
                if not name:
                    QMessageBox.warning(self, "오류", f"종목코드 '{code}'를 찾을 수 없습니다.")
                    return
            else:
                self.log("[시스템] 로그인 전 종목 추가: 종목명은 로그인 후 자동 표시될 수 있습니다.")
            # 종목코드 입력은 바로 추가
            self._add_stock_to_watchlist(code, name)
        else:
            # 종목명으로 검색 - 백그라운드 처리
            if not self.kiwoom or not self.kiwoom.is_connected():
                QMessageBox.warning(self, "오류", "종목명 검색은 로그인 후 가능합니다.")
                return

            # ✅ 캐시가 로드되어 있으면 동기적으로 빠르게 검색
            if self.kiwoom.is_stock_cache_loaded():
                results = self.kiwoom.find_stocks_by_name(input_text)
                self._handle_watchlist_search_results(results, input_text)
            else:
                # 캐시 미로드 시 백그라운드 검색
                self.log(f"[시스템] '{input_text}' 검색 중...")
                self._search_worker = StockSearchWorker(self.kiwoom, input_text)
                self._search_worker.search_finished.connect(
                    lambda results: self._handle_watchlist_search_results(results, input_text)
                )
                self._search_worker.search_error.connect(
                    lambda err: QMessageBox.warning(self, "검색 오류", f"검색 중 오류 발생: {err}")
                )
                self._search_worker.start()

    def _handle_watchlist_search_results(self, results, search_text):
        """종목 검색 결과 처리 (감시종목 추가용)"""
        if not results:
            QMessageBox.warning(self, "검색 결과 없음", f"'{search_text}'에 해당하는 종목을 찾을 수 없습니다.")
            return
        elif len(results) == 1:
            code, name = results[0]
            self._add_stock_to_watchlist(code, name)
        else:
            # 여러 결과가 있으면 사용자에게 선택하도록 함
            items = [f"{r[0]} - {r[1]}" for r in results]
            selected, ok = QInputDialog.getItem(
                self, "종목 선택",
                f"'{search_text}' 검색 결과 ({len(results)}건):",
                items, 0, False
            )
            if ok and selected:
                idx = items.index(selected)
                code, name = results[idx]
                self._add_stock_to_watchlist(code, name)

    def _add_stock_to_watchlist(self, code, name):
        """감시종목에 종목 추가"""
        success, message = self.config.add_to_watchlist(code, name)
        if success:
            self.log(f"[시스템] 감시 종목 추가: {code} {name}")
            self.add_code_input.clear()
            # 부분 갱신: 추가된 종목만 TR 큐에 넣고 전체 갱신은 타이머 유지
            self._append_watchlist_row(code, name)
            self._refresh_watchlist_for_codes([code])
            self._schedule_watchlist_realtime_registration()
        else:
            QMessageBox.warning(self, "오류", message)

    def remove_from_watchlist(self):
        """감시 종목 삭제"""
        selected = self.watchlist_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "선택 오류", "삭제할 종목을 선택해주세요.")
            return

        row = selected[0].row()
        code = self.watchlist_table.item(row, 0).text()

        reply = QMessageBox.question(
            self, "삭제 확인",
            f"종목 '{code}'를 감시 목록에서 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.config.remove_from_watchlist(code)
            self.log(f"[시스템] 감시 종목 삭제: {code}")
            self.refresh_watchlist()

    def resolve_stock_code(self, input_text):
        """종목코드 또는 종목명을 입력받아 종목코드와 종목명을 반환 (캐시 기반 - UI 프리징 없음)

        Args:
            input_text: 종목코드(6자리 숫자) 또는 종목명

        Returns:
            (code, name) 튜플. 실패 시 (None, None) 반환
        """
        if not input_text:
            QMessageBox.warning(self, "입력 오류", "종목코드 또는 종목명을 입력해주세요.")
            return None, None

        # 6자리 숫자인 경우 종목코드로 처리
        if input_text.isdigit() and len(input_text) == 6:
            code = input_text
            if self.kiwoom and self.kiwoom.is_connected():
                # ✅ 캐시에서 먼저 조회 (빠름)
                name = self.kiwoom.get_stock_name_from_cache(code)
                if not name:
                    QMessageBox.warning(self, "오류", f"종목코드 '{code}'를 찾을 수 없습니다.")
                    return None, None
                return code, name
            else:
                return code, ""
        else:
            # 종목명으로 검색 (캐시 기반이면 빠름)
            if not self.kiwoom or not self.kiwoom.is_connected():
                QMessageBox.warning(self, "오류", "종목명 검색은 로그인 후 가능합니다.")
                return None, None

            # ✅ 캐시 기반 검색 (캐시 로드 시 빠름, 미로드 시 기존 방식)
            results = self.kiwoom.find_stocks_by_name(input_text)
            if not results:
                QMessageBox.warning(self, "검색 결과 없음", f"'{input_text}'에 해당하는 종목을 찾을 수 없습니다.")
                return None, None
            elif len(results) == 1:
                return results[0]
            else:
                # 여러 결과가 있으면 사용자에게 선택하도록 함
                items = [f"{r[0]} - {r[1]}" for r in results]
                selected, ok = QInputDialog.getItem(
                    self, "종목 선택",
                    f"'{input_text}' 검색 결과 ({len(results)}건):",
                    items, 0, False
                )
                if ok and selected:
                    idx = items.index(selected)
                    return results[idx]
                else:
                    return None, None

    # =========================
    # 보유종목 선택 / 분석
    # =========================
    def on_holding_selected(self):
        """보유 종목 선택시"""
        selected = self.holdings_table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        code = self.holdings_table.item(row, 0).text()
        name = self.holdings_table.item(row, 1).text()
        quantity = self.holdings_table.item(row, 2).text().replace(",", "")

        self.manual_sell_code.setText(code)
        self.manual_sell_qty.setValue(int(quantity))

        if self.trader:
            analysis = self.trader.get_stock_analysis(code)
            if analysis:
                self.update_analysis_display(code, name, analysis)

    def update_analysis_display(self, code, name, analysis):
        """종목 분석 정보 표시"""
        stock_info = analysis.get("stock_info", {}) or {}
        main_condition = analysis.get("main_condition", {}) or {}
        buy_signal = analysis.get("buy_signal", {}) or {}
        position_summary = analysis.get("position_summary")

        price_txt = self._fmt_int_or_dash(stock_info.get("price"))
        ma_txt = self._fmt_int_or_dash(main_condition.get("ma"))
        lower_txt = self._fmt_int_or_dash(main_condition.get("lower"))

        self.analysis_code_label.setText(f"종목: {code} {name} (현재가: {price_txt}원)")
        self.analysis_ma20_label.setText(f"메인 기준: {ma_txt}원")
        self.analysis_main_condition_label.setText(f"main condition: {lower_txt}원")

        signal_text = buy_signal.get("reason", "-")
        if buy_signal.get("signal"):
            self.analysis_buy_signal_label.setStyleSheet("color: red; font-weight: bold;")
        else:
            self.analysis_buy_signal_label.setStyleSheet("")
        self.analysis_buy_signal_label.setText(f"매수 신호: {signal_text}")

        if position_summary:
            self.analysis_position_label.setText(
                f"포지션: {position_summary['buy_count']}차 매수 / "
                f"평단 {position_summary['avg_price']:,}원 / "
                f"수익률 {position_summary['profit_rate']:.2f}%"
            )

            targets = position_summary.get("sell_targets", [])
            sold = position_summary.get("sold_targets", [])

            self.sell_targets_table.setRowCount(len(targets))
            for i, target in enumerate(targets):
                self.sell_targets_table.setItem(i, 0, QTableWidgetItem(target["name"]))
                self.sell_targets_table.setItem(i, 1, QTableWidgetItem(f"{target['price']:,}원"))

                if target["name"] in sold:
                    status_item = QTableWidgetItem("매도완료")
                    status_item.setForeground(QColor("gray"))
                else:
                    status_item = QTableWidgetItem("대기")
                self.sell_targets_table.setItem(i, 2, status_item)
        else:
            self.analysis_position_label.setText("포지션: 없음")
            self.sell_targets_table.setRowCount(0)

    # =========================
    # 수동매매 / 주문취소
    # =========================
    def on_sell_ratio_changed(self, ratio):
        """비중 변경시 수량 자동 계산"""
        code = self.manual_sell_code.text().strip()
        if not code:
            return

        for row in range(self.holdings_table.rowCount()):
            if self.holdings_table.item(row, 0).text() == code:
                total_qty_str = self.holdings_table.item(row, 2).text().replace(",", "")
                try:
                    total_qty = int(total_qty_str)
                    sell_qty = max(1, int(total_qty * ratio / 100))
                    self.manual_sell_qty.setValue(sell_qty)
                except ValueError:
                    pass
                break

    def do_manual_sell(self):
        """수동 매도 (수량 기준)"""
        if not self.trader:
            return

        input_text = self.manual_sell_code.text().strip()
        quantity = self.manual_sell_qty.value()
        price = self.manual_sell_price.value()

        code, name = self.resolve_stock_code(input_text)
        if not code:
            return

        display_name = f"{code} {name}" if name else code
        reply = QMessageBox.question(
            self, "매도 확인",
            f"종목 {display_name}를 {quantity}주 {'시장가' if price == 0 else f'{price:,}원'}에 매도하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.trader.manual_sell(code, quantity, price)

    def do_manual_sell_by_ratio(self):
        """수동 매도 (비중 기준)"""
        if not self.trader:
            return

        input_text = self.manual_sell_code.text().strip()
        ratio = self.manual_sell_ratio.value()
        price = self.manual_sell_price.value()

        code, name = self.resolve_stock_code(input_text)
        if not code:
            return

        total_qty = 0
        for row in range(self.holdings_table.rowCount()):
            if self.holdings_table.item(row, 0).text() == code:
                total_qty_str = self.holdings_table.item(row, 2).text().replace(",", "")
                try:
                    total_qty = int(total_qty_str)
                except ValueError:
                    pass
                break

        display_name = f"{code} {name}" if name else code
        if total_qty <= 0:
            QMessageBox.warning(self, "오류", f"종목 {display_name}의 보유 수량을 확인할 수 없습니다.")
            return

        sell_qty = max(1, int(total_qty * ratio / 100))

        reply = QMessageBox.question(
            self, "매도 확인",
            f"종목 {display_name}를 {ratio}% ({sell_qty}주/{total_qty}주) "
            f"{'시장가' if price == 0 else f'{price:,}원'}에 매도하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.trader.manual_sell(code, sell_qty, price)

    def do_manual_buy(self):
        """수동 매수"""
        if not self.trader:
            return

        input_text = self.manual_buy_code.text().strip()
        quantity = self.manual_buy_qty.value()
        price = self.manual_buy_price.value()

        code, name = self.resolve_stock_code(input_text)
        if not code:
            return

        display_name = f"{code} {name}" if name else code
        reply = QMessageBox.question(
            self, "매수 확인",
            f"종목 {display_name}를 {quantity}주 {'시장가' if price == 0 else f'{price:,}원'}에 매수하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.trader.manual_buy(code, quantity, price)

    def do_cancel_all_orders(self):
        """전량주문 취소"""
        if not self.kiwoom or not self.kiwoom.is_connected():
            QMessageBox.warning(self, "오류", "키움 API에 연결되어 있지 않습니다.")
            return

        code = self.manual_sell_code.text().strip()
        if not code:
            QMessageBox.warning(self, "입력 오류", "종목코드를 입력해주세요.")
            return

        account = self.account_combo.currentText().strip()
        if not account:
            QMessageBox.warning(self, "오류", "계좌를 선택해주세요.")
            return

        reply = QMessageBox.question(
            self, "전량주문 취소 확인",
            f"종목 {code}의 모든 미체결 주문을 취소하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            cancelled = self.kiwoom.cancel_all_orders_for_stock(account, code)
            if cancelled > 0:
                self.log(f"[{code}] {cancelled}건의 주문이 취소되었습니다.")
                QMessageBox.information(self, "취소 완료", f"{cancelled}건의 주문이 취소되었습니다.")
            else:
                self.log(f"[{code}] 취소할 미체결 주문이 없습니다.")
                QMessageBox.information(self, "알림", "취소할 미체결 주문이 없습니다.")

    # =========================
    # 설정 저장
    # =========================
    def save_settings(self):
        """설정 저장"""
        self.config.set(self.setting_main_condition_period.value(), "buy", "main_condition_period")
        self.config.set(self.setting_main_condition_percent.value(), "buy", "main_condition_percent")
        self.config.set(self.setting_main_condition_buy_percent.value(), "buy", "main_condition_buy_percent")
        self.config.set(self.setting_add_drop.value(), "buy", "additional_buy_drop_percent")
        self.config.set(self.setting_buy_amount.value(), "buy", "buy_amount_per_stock")
        self.config.set(self.setting_max_holding.value(), "buy", "max_holding_stocks")
        # 재진입 허용 설정 삭제됨 - 매도 발생 시 당일 재매수 금지

        self.config.set(
            [self.setting_profit1.value(), self.setting_profit2.value(), self.setting_profit3.value()],
            "sell", "profit_targets"
        )
        self.config.set(
            [self.setting_ratio1.value(), self.setting_ratio2.value(), self.setting_ratio3.value()],
            "sell", "profit_sell_ratios"
        )
        self.config.set(self.setting_ma20_ratio.value(), "sell", "ma20_sell_ratio")

        # 모의투자 설정 삭제됨 - 로그인 시 서버 자동 감지

        self.config.save_config()

        self._update_watchlist_header()

        self.log("[시스템] 설정이 저장되었습니다.")
        QMessageBox.information(self, "저장 완료", "설정이 저장되었습니다.")

    # =========================
    # 미체결 주문 알림 / 종료
    # =========================
    def _check_pending_orders_on_startup(self):
        """프로그램 시작 시 저장된 미체결 주문 확인 및 알림"""
        if not self.trader:
            return

        summary = self.trader.get_pending_orders_summary()
        total = summary["buy_orders"] + summary["sell_orders"]

        if total > 0:
            msg = (
                f"저장된 미체결 주문이 있습니다.\n\n"
                f"- 매수 주문: {summary['buy_orders']}건\n"
                f"- 매도 주문: {summary['sell_orders']}건\n\n"
                f"자동매매를 시작하면 장 시간에 자동으로 복원됩니다.\n"
                f"복원을 원하지 않으면 설정에서 삭제할 수 있습니다."
            )
            self.log(f"[시스템] 저장된 미체결 주문: 매수 {summary['buy_orders']}건, 매도 {summary['sell_orders']}건")
            QMessageBox.information(self, "미체결 주문 복원 알림", msg)
        else:
            self.log("[시스템] 복원할 미체결 주문 없음")

    def closeEvent(self, event):
        """종료시 상태 저장"""
        if self.trader:
            if self.trader.is_running and not self._is_stopping:
                # 종료 중에도 stop이 오래 걸릴 수 있어, UI 종료 시점엔 안전하게 처리
                self._is_stopping = True
                try:
                    self.trader.stop()
                except Exception as e:
                    self.log(f"[시스템] 종료 중 stop 오류: {e}")

            try:
                self.trader.save_current_state()
            except Exception as e:
                self.log(f"[시스템] 종료 중 상태 저장 오류: {e}")

            self.log("[시스템] 상태 저장 완료")

        self.refresh_timer.stop()
        self.trading_timer.stop()
        self.watchlist_refresh_timer.stop()

        if self.scanner and self.scanner.is_running():
            self.scanner.stop()
        if self._scan_progress_dlg:
            self._scan_progress_dlg.hide()

        event.accept()

    # ==========================================================================
    # 종목 스캔 설정 탭
    # ==========================================================================
    def create_scan_settings_tab(self):
        """종목 스캔 설정 탭 (Search 시스템의 설정 기능)"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        w = QWidget()
        scroll.setWidget(w)
        v = QVBoxLayout(w)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(10)

        scan = self.scan_config.get_scan()

        # ── 탐색 대상 ──────────────────────────────────────────────────────
        target_grp = QGroupBox("탐색 대상")
        tg = QGridLayout(target_grp)

        tg.addWidget(QLabel("탐색 시장:"), 0, 0)
        self.sc_market_combo = QComboBox()
        self.sc_market_combo.addItem("코스피 + 코스닥", "both")
        self.sc_market_combo.addItem("코스피만", "kospi")
        self.sc_market_combo.addItem("코스닥만", "kosdaq")
        saved_market = scan.get("market", "both")
        idx_map = {"both": 0, "kospi": 1, "kosdaq": 2}
        self.sc_market_combo.setCurrentIndex(idx_map.get(saved_market, 0))
        tg.addWidget(self.sc_market_combo, 0, 1)

        tg.addWidget(QLabel("거래량 상위"), 1, 0)
        self.sc_top_n_spin = QSpinBox()
        self.sc_top_n_spin.setRange(50, 2000)
        self.sc_top_n_spin.setValue(int(scan.get("top_n", 300)))
        self.sc_top_n_spin.setSuffix(" 종목")
        tg.addWidget(self.sc_top_n_spin, 1, 1)
        tg.addWidget(QLabel("전일 평균 거래량 기준 상위 N종목 탐색"), 1, 2, alignment=Qt.AlignLeft)

        v.addWidget(target_grp)

        # ── 조건 결합 ──────────────────────────────────────────────────────
        mode_grp = QGroupBox("조건 결합 방식")
        mg = QHBoxLayout(mode_grp)
        self.sc_mode_and = QRadioButton("AND (모든 조건 만족)")
        self.sc_mode_or  = QRadioButton("OR  (하나라도 만족)")
        sc_bg = QButtonGroup(self)
        sc_bg.addButton(self.sc_mode_and)
        sc_bg.addButton(self.sc_mode_or)
        if scan.get("condition_mode", "AND") == "AND":
            self.sc_mode_and.setChecked(True)
        else:
            self.sc_mode_or.setChecked(True)
        mg.addWidget(self.sc_mode_and)
        mg.addWidget(self.sc_mode_or)
        mg.addStretch()
        v.addWidget(mode_grp)

        # ── RSI 조건 ───────────────────────────────────────────────────────
        self.sc_rsi_grp = QGroupBox("RSI 조건")
        self.sc_rsi_grp.setCheckable(True)
        self.sc_rsi_grp.setChecked(bool(scan.get("rsi_enabled", True)))
        rg = QGridLayout(self.sc_rsi_grp)

        rg.addWidget(QLabel("RSI 기간:"), 0, 0)
        self.sc_rsi_period = QSpinBox()
        self.sc_rsi_period.setRange(2, 100)
        self.sc_rsi_period.setValue(int(scan.get("rsi_period", 14)))
        rg.addWidget(self.sc_rsi_period, 0, 1)

        rg.addWidget(QLabel("RSI 최솟값 (이상):"), 1, 0)
        self.sc_rsi_min = QDoubleSpinBox()
        self.sc_rsi_min.setRange(0, 100)
        self.sc_rsi_min.setDecimals(1)
        self.sc_rsi_min.setValue(float(scan.get("rsi_min", 0)))
        rg.addWidget(self.sc_rsi_min, 1, 1)

        rg.addWidget(QLabel("RSI 최댓값 (이하):"), 2, 0)
        self.sc_rsi_max = QDoubleSpinBox()
        self.sc_rsi_max.setRange(0, 100)
        self.sc_rsi_max.setDecimals(1)
        self.sc_rsi_max.setValue(float(scan.get("rsi_max", 30)))
        rg.addWidget(self.sc_rsi_max, 2, 1)

        rg.addWidget(QLabel("예) RSI 0~30: 과매도 구간 탐색"), 0, 2, 3, 1, Qt.AlignTop | Qt.AlignLeft)
        v.addWidget(self.sc_rsi_grp)

        # ── 이동평균 조건 ──────────────────────────────────────────────────
        self.sc_ma_grp = QGroupBox("이동평균 조건")
        self.sc_ma_grp.setCheckable(True)
        self.sc_ma_grp.setChecked(bool(scan.get("ma_enabled", False)))
        mag = QGridLayout(self.sc_ma_grp)

        mag.addWidget(QLabel("조건 유형:"), 0, 0)
        self.sc_ma_cond_combo = QComboBox()
        self.sc_ma_cond_combo.addItems(["현재가 > MA (MA 위)", "현재가 < MA (MA 아래)", "골든크로스 (단기 > 장기)"])
        cond_map = {"above": 0, "below": 1, "golden": 2}
        self.sc_ma_cond_combo.setCurrentIndex(cond_map.get(scan.get("ma_condition", "above"), 0))
        self.sc_ma_cond_combo.currentIndexChanged.connect(self._sc_on_ma_cond_changed)
        mag.addWidget(self.sc_ma_cond_combo, 0, 1, 1, 2)

        self.sc_ma_period_lbl = QLabel("이평 기간:")
        mag.addWidget(self.sc_ma_period_lbl, 1, 0)
        self.sc_ma_period = QSpinBox()
        self.sc_ma_period.setRange(1, 200)
        self.sc_ma_period.setValue(int(scan.get("ma_period", 20)))
        mag.addWidget(self.sc_ma_period, 1, 1)

        self.sc_ma_short_lbl = QLabel("단기 기간:")
        self.sc_ma_short_spin = QSpinBox()
        self.sc_ma_short_spin.setRange(1, 100)
        self.sc_ma_short_spin.setValue(int(scan.get("ma_short_period", 5)))
        self.sc_ma_long_lbl = QLabel("장기 기간:")
        self.sc_ma_long_spin = QSpinBox()
        self.sc_ma_long_spin.setRange(1, 200)
        self.sc_ma_long_spin.setValue(int(scan.get("ma_long_period", 20)))

        mag.addWidget(self.sc_ma_short_lbl, 2, 0)
        mag.addWidget(self.sc_ma_short_spin, 2, 1)
        mag.addWidget(self.sc_ma_long_lbl, 3, 0)
        mag.addWidget(self.sc_ma_long_spin, 3, 1)

        v.addWidget(self.sc_ma_grp)
        self._sc_on_ma_cond_changed(self.sc_ma_cond_combo.currentIndex())

        # ── 거래량 조건 ────────────────────────────────────────────────────
        self.sc_vol_grp = QGroupBox("거래량 조건")
        self.sc_vol_grp.setCheckable(True)
        self.sc_vol_grp.setChecked(bool(scan.get("volume_enabled", True)))
        vg = QGridLayout(self.sc_vol_grp)

        vg.addWidget(QLabel("평균 기간 (일):"), 0, 0)
        self.sc_vol_days = QSpinBox()
        self.sc_vol_days.setRange(1, 120)
        self.sc_vol_days.setValue(int(scan.get("volume_avg_days", 20)))
        vg.addWidget(self.sc_vol_days, 0, 1)

        vg.addWidget(QLabel("배수 (이상):"), 1, 0)
        self.sc_vol_ratio = QDoubleSpinBox()
        self.sc_vol_ratio.setRange(0.1, 100)
        self.sc_vol_ratio.setDecimals(1)
        self.sc_vol_ratio.setValue(float(scan.get("volume_ratio", 2.0)))
        self.sc_vol_ratio.setSuffix(" 배")
        vg.addWidget(self.sc_vol_ratio, 1, 1)

        vg.addWidget(QLabel("예) 20일 평균 거래량의 2배 이상이면 조건 만족"), 0, 2, 2, 1, Qt.AlignTop | Qt.AlignLeft)
        v.addWidget(self.sc_vol_grp)

        # ── 가격 돌파 조건 ─────────────────────────────────────────────────
        self.sc_bo_grp = QGroupBox("가격 돌파 조건")
        self.sc_bo_grp.setCheckable(True)
        self.sc_bo_grp.setChecked(bool(scan.get("breakout_enabled", False)))
        bg2 = QGridLayout(self.sc_bo_grp)

        bg2.addWidget(QLabel("기간 (일):"), 0, 0)
        self.sc_bo_days = QSpinBox()
        self.sc_bo_days.setRange(1, 250)
        self.sc_bo_days.setValue(int(scan.get("breakout_days", 20)))
        bg2.addWidget(self.sc_bo_days, 0, 1)
        bg2.addWidget(QLabel("예) 20일 고가 돌파 시 조건 만족"), 0, 2, Qt.AlignLeft)
        v.addWidget(self.sc_bo_grp)

        # ── 수급 조건 ──────────────────────────────────────────────────────
        self.sc_supply_grp = QGroupBox("수급 조건  ※ 활성화 시 종목당 TR 1회 추가 (탐색 시간 증가)")
        self.sc_supply_grp.setCheckable(True)
        self.sc_supply_grp.setChecked(bool(scan.get("supply_enabled", False)))
        sg = QGridLayout(self.sc_supply_grp)

        sg.addWidget(QLabel("외국인 순매수 연속 (일):"), 0, 0)
        self.sc_foreign_consec_spin = QSpinBox()
        self.sc_foreign_consec_spin.setRange(0, 20)
        self.sc_foreign_consec_spin.setValue(int(scan.get("foreign_consec_days", 3)))
        self.sc_foreign_consec_spin.setSpecialValueText("사용 안 함")
        sg.addWidget(self.sc_foreign_consec_spin, 0, 1)

        self.sc_institution_turnover_chk = QCheckBox("기관 순매수 전환 (오늘 > 0)")
        self.sc_institution_turnover_chk.setChecked(bool(scan.get("institution_turnover_enabled", True)))
        sg.addWidget(self.sc_institution_turnover_chk, 1, 0, 1, 2)

        sg.addWidget(QLabel("예) 외국인 3일 연속 순매수\n+ 기관 순매수 전환"),
                     0, 2, 2, 1, Qt.AlignTop | Qt.AlignLeft)
        v.addWidget(self.sc_supply_grp)

        # ── 거래대금 조건 ──────────────────────────────────────────────────
        self.sc_tv_grp = QGroupBox("거래대금 조건")
        self.sc_tv_grp.setCheckable(True)
        self.sc_tv_grp.setChecked(bool(scan.get("trading_value_enabled", False)))
        tvg = QGridLayout(self.sc_tv_grp)

        tvg.addWidget(QLabel("거래대금 최소 (억원):"), 0, 0)
        self.sc_tv_min_spin = QDoubleSpinBox()
        self.sc_tv_min_spin.setRange(0, 100000)
        self.sc_tv_min_spin.setDecimals(0)
        self.sc_tv_min_spin.setValue(float(scan.get("trading_value_min_billion", 100)))
        self.sc_tv_min_spin.setSuffix(" 억원")
        tvg.addWidget(self.sc_tv_min_spin, 0, 1)

        self.sc_tv_increase_chk = QCheckBox("거래대금 증가율 조건 사용")
        self.sc_tv_increase_chk.setChecked(bool(scan.get("trading_value_increase_enabled", False)))
        tvg.addWidget(self.sc_tv_increase_chk, 1, 0, 1, 2)
        self.sc_tv_increase_chk.toggled.connect(self._sc_on_tv_increase_toggled)

        tvg.addWidget(QLabel("증가율 기준 (이상):"), 2, 0)
        self.sc_tv_ratio_spin = QDoubleSpinBox()
        self.sc_tv_ratio_spin.setRange(100, 10000)
        self.sc_tv_ratio_spin.setDecimals(0)
        self.sc_tv_ratio_spin.setValue(float(scan.get("trading_value_increase_pct", 200)))
        self.sc_tv_ratio_spin.setSuffix(" %")
        tvg.addWidget(self.sc_tv_ratio_spin, 2, 1)

        tvg.addWidget(QLabel("평균 기간 (일):"), 3, 0)
        self.sc_tv_avg_days_spin = QSpinBox()
        self.sc_tv_avg_days_spin.setRange(1, 120)
        self.sc_tv_avg_days_spin.setValue(int(scan.get("trading_value_avg_days", 20)))
        tvg.addWidget(self.sc_tv_avg_days_spin, 3, 1)

        tvg.addWidget(QLabel("예) 거래대금 > 100억\n20일 평균 대비 200% 이상"),
                      0, 2, 4, 1, Qt.AlignTop | Qt.AlignLeft)
        v.addWidget(self.sc_tv_grp)
        self._sc_on_tv_increase_toggled(self.sc_tv_increase_chk.isChecked())

        # ── 저장 버튼 ──────────────────────────────────────────────────────
        save_row = QHBoxLayout()
        save_row.addStretch()
        save_btn = QPushButton("설정 저장")
        save_btn.setMinimumWidth(120)
        save_btn.setStyleSheet("background:#2196F3; color:white; font-weight:bold;")
        save_btn.clicked.connect(self._save_scan_settings)
        save_row.addWidget(save_btn)
        v.addLayout(save_row)

        v.addStretch()
        return scroll

    # ==========================================================================
    # 탐색 종목 탭
    # ==========================================================================
    def create_scan_results_tab(self):
        """탐색 종목 탭 (Search 시스템의 스캔 결과 테이블)"""
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(6, 6, 6, 4)

        # 진행 바
        prog_row = QHBoxLayout()
        self.sc_progress_bar = QProgressBar()
        self.sc_progress_bar.setRange(0, 100)
        self.sc_progress_bar.setValue(0)
        self.sc_progress_bar.setTextVisible(True)
        self.sc_progress_bar.setFormat("대기 중")
        self.sc_progress_bar.setFixedHeight(20)
        prog_row.addWidget(self.sc_progress_bar, 1)

        self.sc_progress_lbl = QLabel("")
        self.sc_progress_lbl.setStyleSheet("font-size:9pt; color:#333;")
        prog_row.addWidget(self.sc_progress_lbl)
        v.addLayout(prog_row)

        # 결과 요약
        summary_row = QHBoxLayout()
        self.sc_result_count_lbl = QLabel("탐색 결과: -")
        self.sc_result_count_lbl.setStyleSheet("font-weight:bold;")
        summary_row.addWidget(self.sc_result_count_lbl)
        summary_row.addStretch()

        self.sc_last_scan_lbl = QLabel("마지막 갱신: -")
        self.sc_last_scan_lbl.setStyleSheet("font-size:9pt; color:#555;")
        summary_row.addWidget(self.sc_last_scan_lbl)

        self.sc_add_to_watchlist_btn = QPushButton("종목 추가")
        self.sc_add_to_watchlist_btn.setFixedHeight(24)
        self.sc_add_to_watchlist_btn.clicked.connect(self._add_scan_result_to_watchlist)
        summary_row.addWidget(self.sc_add_to_watchlist_btn)

        v.addLayout(summary_row)

        # 결과 테이블
        self.sc_result_table = QTableWidget()
        self.sc_result_table.setColumnCount(9)
        self.sc_result_table.setHorizontalHeaderLabels([
            "종목명 (코드)", "현재가", "RSI", "이평(MA)", "거래량비", "돌파",
            "수급", "거래대금", "조건"
        ])
        hdr = self.sc_result_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        for c in range(1, 9):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.sc_result_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.sc_result_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.sc_result_table.setAlternatingRowColors(True)
        self.sc_result_table.verticalHeader().setVisible(False)
        self.sc_result_table.setSortingEnabled(True)
        v.addWidget(self.sc_result_table, 1)

        return w

    # ==========================================================================
    # 종목 스캔 관련 메서드
    # ==========================================================================
    def _sc_on_ma_cond_changed(self, idx):
        is_golden = (idx == 2)
        self.sc_ma_period_lbl.setVisible(not is_golden)
        self.sc_ma_period.setVisible(not is_golden)
        self.sc_ma_short_lbl.setVisible(is_golden)
        self.sc_ma_short_spin.setVisible(is_golden)
        self.sc_ma_long_lbl.setVisible(is_golden)
        self.sc_ma_long_spin.setVisible(is_golden)

    def _sc_on_tv_increase_toggled(self, checked):
        self.sc_tv_ratio_spin.setEnabled(checked)
        self.sc_tv_avg_days_spin.setEnabled(checked)

    def _save_scan_settings(self):
        """스캔 설정 저장"""
        cond_map = {0: "above", 1: "below", 2: "golden"}
        scan = {
            "market":            self.sc_market_combo.currentData(),
            "condition_mode":    "AND" if self.sc_mode_and.isChecked() else "OR",
            "top_n":             self.sc_top_n_spin.value(),
            "rsi_enabled":       self.sc_rsi_grp.isChecked(),
            "rsi_period":        self.sc_rsi_period.value(),
            "rsi_min":           self.sc_rsi_min.value(),
            "rsi_max":           self.sc_rsi_max.value(),
            "ma_enabled":        self.sc_ma_grp.isChecked(),
            "ma_period":         self.sc_ma_period.value(),
            "ma_condition":      cond_map[self.sc_ma_cond_combo.currentIndex()],
            "ma_short_period":   self.sc_ma_short_spin.value(),
            "ma_long_period":    self.sc_ma_long_spin.value(),
            "volume_enabled":    self.sc_vol_grp.isChecked(),
            "volume_avg_days":   self.sc_vol_days.value(),
            "volume_ratio":      self.sc_vol_ratio.value(),
            "breakout_enabled":  self.sc_bo_grp.isChecked(),
            "breakout_days":     self.sc_bo_days.value(),
            "supply_enabled":                self.sc_supply_grp.isChecked(),
            "foreign_consec_days":           self.sc_foreign_consec_spin.value(),
            "institution_turnover_enabled":  self.sc_institution_turnover_chk.isChecked(),
            "trading_value_enabled":         self.sc_tv_grp.isChecked(),
            "trading_value_min_billion":     self.sc_tv_min_spin.value(),
            "trading_value_increase_enabled": self.sc_tv_increase_chk.isChecked(),
            "trading_value_increase_pct":    self.sc_tv_ratio_spin.value(),
            "trading_value_avg_days":        self.sc_tv_avg_days_spin.value(),
        }
        if self.scan_config.save_scan(scan):
            self.log("[스캔설정] 저장 완료")
            if self.scanner and self.scanner.is_running():
                self.scanner.apply_new_conditions()
            QMessageBox.information(self, "설정 저장", "스캔 설정이 저장되었습니다.")
        else:
            QMessageBox.warning(self, "저장 실패", "스캔 설정 저장에 실패했습니다.")

    def _toggle_scan(self):
        if self.scanner and self.scanner.is_running():
            self._stop_scan()
        else:
            self._start_scan()

    def _start_scan(self):
        if not self.kiwoom:
            QMessageBox.warning(self, "오류", "먼저 로그인해주세요.")
            return

        self._scan_progress_dlg = ScanProgressDialog(
            cancel_callback=self._stop_scan,
            parent=self,
        )
        self._scan_progress_dlg.show()

        self.scanner = StockScanner(
            kiwoom      = self.kiwoom,
            config      = self.scan_config,
            log_cb      = self.log,
            progress_cb = self._on_scan_progress,
            result_cb   = self._on_scan_result,
            done_cb     = self._on_scan_done,
        )
        self.scanner.start()

        self.scan_btn.setText("자동탐색 중지")
        self.scan_btn.setStyleSheet(
            "background-color: #f44336; color: white; font-weight: bold; padding: 10px 20px;"
        )
        self.sc_progress_bar.setFormat("스캔 중...")
        self.log("[탐색] 자동탐색 시작")
        self._scan_countdown_timer.start(1000)

    def _stop_scan(self):
        if self.scanner:
            self.scanner.stop()
        self._scan_countdown_timer.stop()
        if self._scan_progress_dlg:
            self._scan_progress_dlg.hide()
            self._scan_progress_dlg = None
        if hasattr(self, 'scan_btn'):
            self.scan_btn.setText("자동탐색 시작")
            self.scan_btn.setStyleSheet(
                "background-color: #FF9800; color: white; font-weight: bold; padding: 10px 20px;"
            )
        if hasattr(self, 'sc_progress_bar'):
            self.sc_progress_bar.setFormat("중지됨")
            self.sc_progress_bar.setValue(0)
        self.log("[탐색] 자동탐색 중지")

    def _on_scan_progress(self, phase, done, total, name):
        if self._scan_progress_dlg:
            self._scan_progress_dlg.update(phase, done, total, name)
        if hasattr(self, 'sc_progress_bar') and total > 0:
            pct = int(done / total * 100)
            self.sc_progress_bar.setValue(pct)
            self.sc_progress_bar.setFormat(f"{phase}  {done}/{total}")
            self.sc_progress_lbl.setText(name)

    def _on_scan_done(self):
        if self._scan_progress_dlg:
            self._scan_progress_dlg.mark_done()
        if hasattr(self, 'sc_progress_bar'):
            self.sc_progress_bar.setFormat("완료")
            self.sc_progress_lbl.setText("")

    def _on_scan_result(self, results):
        self._scan_result_cache = {r["code"]: r for r in results}
        self._schedule_scan_table_refresh()
        now = datetime.datetime.now().strftime("%H:%M:%S")
        if hasattr(self, 'sc_last_scan_lbl'):
            self.sc_last_scan_lbl.setText(f"마지막 갱신: {now}")
            self.sc_result_count_lbl.setText(f"탐색 결과: {len(results)}종목")
        self.log(f"[탐색결과] {len(results)}종목 탐색됨 ({now})")

    def _add_scan_result_to_watchlist(self):
        """탐색 종목 탭에서 선택한 종목을 감시 종목에 추가"""
        selected = self.sc_result_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "선택 오류", "추가할 종목을 선택해주세요.")
            return
        row = selected[0].row()
        cell_text = self.sc_result_table.item(row, 0).text()  # "종목명 (코드)"
        try:
            code = cell_text.rsplit("(", 1)[-1].rstrip(")")
            name = cell_text.rsplit(" (", 1)[0]
        except Exception:
            QMessageBox.warning(self, "오류", "종목 정보를 파싱할 수 없습니다.")
            return
        success, message = self.config.add_to_watchlist(code, name)
        if success:
            self.log(f"[시스템] 감시 종목 추가 (탐색): {code} {name}")
            self._append_watchlist_row(code, name)
            self._refresh_watchlist_for_codes([code])
            self._schedule_watchlist_realtime_registration()
            QMessageBox.information(self, "추가 완료", f"{name} ({code}) 종목이 감시 종목에 추가되었습니다.")
        else:
            QMessageBox.warning(self, "오류", message)

    def _refresh_scan_table(self):
        self._schedule_scan_table_refresh()

    def _sc_set(self, r, c, text, align=Qt.AlignLeft | Qt.AlignVCenter):
        self.sc_result_table.setItem(r, c, self._sc_make_item(text, align))

    @staticmethod
    def _sc_make_item(text, align=Qt.AlignLeft | Qt.AlignVCenter):
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(align)
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        return item

    def _tick_scan_countdown(self):
        if not self.scanner or not self.scanner.is_running():
            return
        if not hasattr(self, 'scan_btn'):
            return
        if self.scanner.is_scanning():
            elapsed = self.scanner.get_scan_elapsed_seconds()
            m, s = divmod(elapsed, 60)
            self.scan_btn.setToolTip(f"탐색 경과: {m:02d}:{s:02d}")
            return
        remaining = self.scanner.get_next_refresh_remaining_seconds()
        if remaining is not None:
            m, s = divmod(remaining, 60)
            self.scan_btn.setToolTip(f"다음 갱신: {m:02d}:{s:02d}")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 사용 기간 체크
    today = datetime.date.today()
    expiry_date = datetime.date(2026, 4, 8)

    if today > expiry_date:
        QMessageBox.critical(None, "사용 기간 만료",
            "프로그램 사용 기간이 만료되었습니다.\n관리자에게 문의해 주세요.\n"
            f"kanu: moozartjkk@gmail.com")
        sys.exit(0)

    if today.year == 2026 and today.month == 3:
        remaining = (expiry_date - today).days
        QMessageBox.warning(None, "사용 기간 안내",
            f"프로그램 사용 기간이 {remaining}일 남았습니다.\n"
            f"만료일: 2026년 4월 8일\n\n"
            f"계속 사용하시려면 관리자에게 문의해 주세요.\n"
            f"kanu: moozartjkk@gmail.com")

    dlg = DisclaimerDialog()
    if dlg.exec_() != QDialog.Accepted:
        sys.exit(0)

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
