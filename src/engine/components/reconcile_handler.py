"""src/engine/components/reconcile_handler.py

Detects positions that were closed externally (manual MT5 close, SL/TP hit
server-side, broker intervention) and records a proper TradeResult so that
risk state, strategy state, and the data log stay consistent.
"""
from src.domain.enums           import TradeStatus
from src.domain.market_data     import MarketSnapshot
from src.domain.trading         import TradeResult
from src.engine.components.trading_config import TradingConfig
from src.infrastructure.logger.data_logger import DataLogger
from src.infrastructure.logger.logger import log
from src.brokers.mt5_components.retcode_mapper import map_deal_reason


def check_manual_closes(
    bridge,
    position_manager,
    risk_manager,
    strategy,
    snapshot: MarketSnapshot,
    datalogger: DataLogger,
    config: TradingConfig,
) -> int:
    """
    Compare _position_metadata against live MT5 positions.
    Any ticket present in metadata but absent in MT5 was closed externally.
    Builds a TradeResult, logs it, and cleans up metadata.

    Returns the number of externally-closed positions detected.
    """
    if not position_manager._position_metadata:
        return 0

    # Live tickets that belong to this strategy
    live_positions = position_manager.get_strategy_positions(config.symbol, strategy.magic_number)
    live_tickets = {int(p.ticket) for p in live_positions}

    # Tickets tracked in metadata
    meta_tickets = set(position_manager._position_metadata.keys())
    ghost_tickets = meta_tickets - live_tickets

    if not ghost_tickets:
        return 0

    detected = 0

    for ticket in ghost_tickets:
        meta = position_manager._position_metadata.get(ticket)
        if meta is None:
            continue

        # ── Fetch deal history ────────────────────────────────────────
        try:
            deals = bridge.history_deals_get_by_position(ticket)
        except Exception as exc:
            log(f"[RECONCILE] Failed to fetch deals for ticket={ticket}: {exc}", level="ERROR")
            continue

        if not deals:
            # MT5 history not yet available (race condition on very fast closes). Leave metadata intact; will be caught on next tick.
            log(
                f"[RECONCILE] No deal history yet for ticket={ticket}, will retry",
                level="WARNING",
            )
            continue
        
        # MT5 deal entry: 0=IN, 1=OUT, 2=IN/OUT
        entry_deals     = [d for d in deals if d.entry == 0]
        exit_deals      = [d for d in deals if d.entry == 1]
        if not exit_deals:
            inout_deals = [d for d in deals if d.entry == 2]
            if inout_deals:
                exit_deal = inout_deals[-1]
            else:
                log(
                    f"[RECONCILE] No exit deal for ticket={ticket} — will retry next tick",
                    level="WARNING",
                )
                continue
        else:
            exit_deal = exit_deals[-1]  # most recent exit (handles partial closes)

        # ── Calculate duration ────────────────────────────────────────
        entry_time = None
        if entry_deals:
            entry_time = entry_deals[0].timestamp
        else:
            entry_time = meta.get("entry_fill_time")  # Bug #3d fix
 
        duration_min = None
        if entry_time and exit_deal.timestamp:
            try:
                duration_min = (exit_deal.timestamp - entry_time).total_seconds() / 60.0
            except Exception:
                duration_min = None
 
        # ── Aggregate financials ──────────────────────────────────────
        net_pnl    = sum(d.profit     for d in deals)
        total_fees = sum((d.commission or 0.0) + (d.swap or 0.0) + (d.fee or 0.0)for d in deals)

        # ── Determine exit reason based on MT5 deal reason ────────────
        exit_reason = map_deal_reason(getattr(exit_deal, "reason", 0))
        if getattr(exit_deal, "reason", 0) == 1:  # expert
            if entry_deals:
                entry_deal = entry_deals[0]
                if entry_deal.type == 0:  # mt5.DEAL_TYPE_BUY
                    exit_reason = "bollinger_lower_cross"
                elif entry_deal.type == 1:  # mt5.DEAL_TYPE_SELL
                    exit_reason = "bollinger_upper_cross"

        trade_result = TradeResult(
            setup_id                = meta.get("setup_id"),
            position_id             = ticket,
            order                   = exit_deal.ticket,
            symbol                  = config.symbol,
            volume                  = exit_deal.volume,
            exit_price              = exit_deal.price,
            exit_time               = exit_deal.timestamp,
            exit_reason             = exit_reason,
            exit_bid                = snapshot.tick.bid,
            exit_ask                = snapshot.tick.ask,
            total_fees              = total_fees,
            net_pnl                 = net_pnl,
            duration_minutes        = duration_min,
            risk_reward_ratio       = None,
            max_adverse_excursion   = meta.get("mae", 0.0),
            max_favorable_excursion = meta.get("mfe", 0.0),
            is_recovered            = False,
            status                  = TradeStatus.CLOSED,
        )

        try:
            risk_manager.update(trade_result)
            strategy.update_trade_result(trade_result)
        except Exception as exc:
            log(f"[RECONCILE] State update failed for ticket={ticket}: {exc}", level="ERROR")
            continue

        datalogger.log_trade_result(trade_result)
        position_manager.remove_metadata(ticket)
        detected += 1
 
        log(
            f"[RECONCILE] {exit_reason.upper()} close — ticket={ticket}, exit={exit_deal.price:.5f}, pnl={net_pnl:.2f}, duration={f'{duration_min:.1f}min' if duration_min else 'unknown'}",
            level="WARNING",
        )
 
    return detected