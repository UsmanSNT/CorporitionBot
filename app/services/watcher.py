import logging
from datetime import datetime

from sqlalchemy.orm import Session
from telegram.ext import Application

from app.database import get_session
from app.models import WatchRule, Notification, SystemState, User
from app.sources.cooperation import CooperationSource
from app.sources.new_cooperation import NewCooperationSource
from app.sources.xt_xarid import XtXaridSource
from app.services.listing_service import upsert_listing
from app.services.matcher import find_matching_rules
from app.services.price_service import get_previous_price
from app.bot.notifications import send_new_listing_notification, send_price_drop_notification

logger = logging.getLogger(__name__)

_cooperation = CooperationSource()
_new_cooperation = NewCooperationSource()
_xt_xarid = XtXaridSource()

SOURCE_STATUS: dict[str, str] = {
    "cooperation": "unknown",
    "new_cooperation": "unknown",
    "xt_xarid": "unknown",
}


async def run_check(app: Application) -> None:
    logger.info("Watcher: starting check cycle")
    start = datetime.utcnow()

    with get_session() as session:
        rules = session.query(WatchRule).filter_by(enabled=True).all()
        users = {u.id: u for u in session.query(User).all()}

        # Collect keywords to search
        keywords = list({r.keyword for r in rules if r.keyword})
        if not keywords:
            keywords = [""]  # fetch latest if no rules

        for source_name, source in [
            ("cooperation", _cooperation),
            ("new_cooperation", _new_cooperation),
            ("xt_xarid", _xt_xarid),
        ]:
            try:
                ok = await source.health_check()
                SOURCE_STATUS[source_name] = "ok" if ok else "error"
                if not ok:
                    logger.warning(f"Watcher: {source_name} is not reachable, skipping")
                    continue

                all_data = []
                for keyword in keywords:
                    if keyword:
                        data = await source.search(keyword)
                    else:
                        data = await source.get_latest()
                    all_data.extend(data)

                logger.info(f"Watcher: {source_name} returned {len(all_data)} listings")

                for item in all_data:
                    try:
                        listing, is_new, price_changed = upsert_listing(session, item)

                        # Find matching rules for this listing
                        matching = find_matching_rules(listing, rules)

                        for rule in matching:
                            user = users.get(rule.user_id)
                            if not user:
                                continue

                            if is_new and rule.notify_new:
                                already_sent = session.query(Notification).filter_by(
                                    listing_id=listing.id,
                                    user_id=user.id,
                                    notification_type="new",
                                ).first()
                                if not already_sent:
                                    await send_new_listing_notification(app.bot, user, listing, rule)
                                    session.add(Notification(
                                        user_id=user.id,
                                        watch_rule_id=rule.id,
                                        listing_id=listing.id,
                                        notification_type="new",
                                        price=listing.price,
                                    ))

                            elif price_changed and rule.notify_price_drop:
                                old_price = get_previous_price(session, listing.id)
                                if old_price and listing.price and listing.price < old_price:
                                    already_sent = session.query(Notification).filter_by(
                                        listing_id=listing.id,
                                        user_id=user.id,
                                        notification_type="price_drop",
                                        price=listing.price,
                                    ).first()
                                    if not already_sent:
                                        await send_price_drop_notification(app.bot, user, listing, rule, old_price)
                                        session.add(Notification(
                                            user_id=user.id,
                                            watch_rule_id=rule.id,
                                            listing_id=listing.id,
                                            notification_type="price_drop",
                                            price=listing.price,
                                        ))
                    except Exception as e:
                        logger.error(f"Watcher: error processing listing {item.external_id}: {e}")

                SOURCE_STATUS[source_name] = "ok"

            except Exception as e:
                SOURCE_STATUS[source_name] = f"error: {e}"
                logger.error(f"Watcher: {source_name} check failed: {e}")

        # Save last check time
        state = session.get(SystemState, "last_check")
        if state is None:
            state = SystemState(key="last_check")
            session.add(state)
        state.value = datetime.utcnow().isoformat()

    elapsed = (datetime.utcnow() - start).total_seconds()
    logger.info(f"Watcher: check cycle done in {elapsed:.1f}s")
