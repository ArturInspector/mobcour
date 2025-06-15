from datetime import datetime
import logging
from database import Database

logger = logging.getLogger(__name__)
db = Database()
# Not using! User statistic, sklearn in future version.

def calculate_user_statistics(user_id: int) -> dict:
    try:
        sessions = db.get_user_sessions(user_id)
        if not sessions:
            return {
                'total_shifts': 0,
                'total_hours': 0,
                'total_earnings': 0,
                'total_orders': 0,
                'avg_shift_duration': 0,
                'avg_earnings_per_hour': 0
            }

        total_hours = 0
        total_earnings = 0
        total_orders = 0

        for session in sessions:
            if session.get('start_time') and session.get('end_time'):
                start_dt = datetime.strptime(session['start_time'], '%Y-%m-%d %H:%M:%S')
                end_dt = datetime.strptime(session['end_time'], '%Y-%m-%d %H:%M:%S')
                session_hours = (end_dt - start_dt).total_seconds() / 3600
                total_hours += session_hours
            
            total_earnings += session.get('earnings', 0)
            total_orders += session.get('order_count', 0)

        avg_shift_duration = total_hours / len(sessions) if sessions else 0
        avg_earnings_per_hour = total_earnings / total_hours if total_hours > 0 else 0

        return {
            'total_shifts': len(sessions),
            'total_hours': round(total_hours, 2),
            'total_earnings': round(total_earnings, 2),
            'total_orders': total_orders,
            'avg_shift_duration': round(avg_shift_duration, 2),
            'avg_earnings_per_hour': round(avg_earnings_per_hour, 2)
        }
    except Exception as e:
        logger.error(f"Error calculating statistics for user {user_id}: {e}")
        return None