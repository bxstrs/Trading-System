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
    live_positions = bridge.get_positions(config.symbol)
    live_tickets = {
        int(p.ticket)
        for p in live_positions
        if p.comment == str(strategy.strategy_id)
    }

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
        
        if meta.get("reconciled"):
            position_manager.remove_metadata(ticket)
            continue

        # Fetch all deals for this position to reconstruct exit
        try:
            deals = bridge.history_deals_get_by_position(ticket)
        except Exception as exc:
            log(f"[RECONCILE] Failed to fetch deals for ticket={ticket}: {exc}", level="ERROR")
            continue

        if not deals:
            # MT5 history not yet available (race condition on very fast closes).
            # Leave metadata intact; will be caught on next tick.
            log(
                f"[RECONCILE] No deal history yet for ticket={ticket}, will retry",
                level="WARNING",
            )
            continue
        
        meta["reconciled"] = True
        position_manager._position_metadata[ticket] = meta
        
        # MT5 deal entry: 0=IN, 1=OUT, 2=IN/OUT
        entry_deals     = [d for d in deals if d.entry == 0]
        exit_deal       = [d for d in deals if d.entry == 1][-1] or deals  # fallback to all
        entry_time      = entry_deals[0].timestamp if entry_deals else exit_deal.timestamp
        duration_min    = (exit_deal.timestamp - entry_time).total_seconds() / 60.0

        net_pnl    = sum(d.profit for d in deals)
        total_fees = sum((d.commission or 0) + (d.swap or 0) + (d.fee or 0) for d in deals)

        trade_result = TradeResult(
            setup_id                = meta.get("setup_id"),
            position_id             = ticket,
            order                   = exit_deal.ticket,
            symbol                  = config.symbol,
            volume                  = exit_deal.volume,
            exit_price              = exit_deal.price,
            exit_time               = exit_deal.timestamp,
            exit_reason             = "manual_close",
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

        datalogger.log_trade_result(trade_result)
        risk_manager.update(trade_result)
        strategy.update_trade_result(trade_result)
        position_manager.remove_metadata(ticket)
        detected += 1

        log(
            f"[RECONCILE] Manual close detected — ticket={ticket}, "
            f"exit={exit_deal.price:.5f}, pnl={net_pnl:.2f}",
            level="WARNING",
        )

    return detected