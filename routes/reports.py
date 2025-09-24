"""
Report routes for weekly, monthly, and custom period reports with aggregation
"""

from flask import Blueprint, g, request
from utils.decorators import jwt_required_custom, role_required, rate_limit
from utils.validators import validate_date_range
from utils.helpers import (
    format_response, 
    get_date_range_for_week, 
    get_date_range_for_month,
    parse_date_from_string,
    generate_weekly_summary,
    calculate_cycle_progress
)
from models.entry import Entry
from models.user import User
from models.level import Level
from datetime import datetime, date, timedelta
from bson import ObjectId
import calendar

reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/weekly', methods=['GET'])
@jwt_required_custom
@role_required('Murabi', 'Masool', 'Sheikh', 'Admin')
@rate_limit(max_requests=30, window_minutes=60)
def weekly_report():
    """Generate weekly report for Murabi and above"""
    current_user = g.current_user
    
    # Get query parameters
    user_id = request.args.get('user_id')
    week_offset = int(request.args.get('week_offset', 0))  # 0 = current week, -1 = last week, etc.
    
    # Calculate week date range
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    end_of_week = start_of_week + timedelta(days=6)
    
    # Determine target users based on role and permissions
    target_users = []
    
    if user_id:
        # Specific user requested
        user = User.find_by_id(user_id)
        if not user:
            return format_response(
                success=False,
                message="User not found",
                status_code=404
            )
        
        # Check permissions
        can_view = False
        if current_user.role == 'Admin':
            can_view = True
        elif current_user.role == 'Murabi' and str(user.murabi_id) == str(current_user._id):
            can_view = True
        elif current_user.role in ['Masool', 'Sheikh'] and User.is_in_hierarchy(user._id, current_user._id):
            can_view = True
        
        if not can_view:
            return format_response(
                success=False,
                message="Insufficient permissions to view this user's report",
                status_code=403
            )
        
        target_users = [user]
    
    else:
        # Get users based on role hierarchy
        if current_user.role == 'Admin':
            target_users = User.find_by_role('Saalik')
        elif current_user.role == 'Sheikh':
            target_users = User.find_by_hierarchy(current_user._id, role_filter='Saalik')
        elif current_user.role == 'Masool':
            target_users = User.find_by_murabi_hierarchy(current_user._id, role_filter='Saalik')
        elif current_user.role == 'Murabi':
            target_users = User.find_by_murabi_id(current_user._id)
    
    # Generate reports for each user
    user_reports = []
    overall_stats = {
        'total_users': len(target_users),
        'active_users': 0,
        'total_entries': 0,
        'zikr_completion_rate': 0,
        'cycle_violations': 0
    }
    
    for user in target_users:
        # Get user's entries for the week
        entries = Entry.find_by_user(user._id, start_date=start_of_week, end_date=end_of_week)
        
        # Generate summary
        summary = generate_weekly_summary(user, start_of_week, end_of_week)
        cycle_progress = calculate_cycle_progress(user)
        
        # Calculate user stats
        user_stats = {
            'user_id': str(user._id),
            'name': user.name,
            'phone': user.phone,
            'level': user.level,
            'murabi_name': None,
            'entries_count': len(entries),
            'days_submitted': summary.get('days_with_entries', 0),
            'zikr_completion_rate': summary.get('zikr_completion_percentage', 0),
            'cycle_progress': cycle_progress,
            'violations': summary.get('violations', []),
            'last_entry_date': None
        }
        
        # Get Murabi name
        if user.murabi_id:
            murabi = User.find_by_id(user.murabi_id)
            if murabi:
                user_stats['murabi_name'] = murabi.name
        
        # Get last entry date
        if entries:
            user_stats['last_entry_date'] = max(entry.date for entry in entries).isoformat()
        
        user_reports.append(user_stats)
        
        # Update overall stats
        if len(entries) > 0:
            overall_stats['active_users'] += 1
        overall_stats['total_entries'] += len(entries)
        overall_stats['cycle_violations'] += len(summary.get('violations', []))
    
    # Calculate overall completion rate
    if overall_stats['total_users'] > 0:
        total_completion = sum(report['zikr_completion_rate'] for report in user_reports)
        overall_stats['zikr_completion_rate'] = total_completion / overall_stats['total_users']
    
    return format_response(
        success=True,
        message="Weekly report generated successfully",
        data={
            'period': {
                'type': 'weekly',
                'start_date': start_of_week.isoformat(),
                'end_date': end_of_week.isoformat(),
                'week_offset': week_offset
            },
            'overall_stats': overall_stats,
            'user_reports': user_reports,
            'generated_by': {
                'user_id': str(current_user._id),
                'name': current_user.name,
                'role': current_user.role
            },
            'generated_at': datetime.utcnow().isoformat()
        }
    )

@reports_bp.route('/monthly', methods=['GET'])
@jwt_required_custom
@role_required('Masool', 'Sheikh', 'Admin')
@rate_limit(max_requests=20, window_minutes=60)
def monthly_report():
    """Generate monthly report for Masool and above"""
    current_user = g.current_user
    
    # Get query parameters
    year = int(request.args.get('year', date.today().year))
    month = int(request.args.get('month', date.today().month))
    user_id = request.args.get('user_id')
    
    # Validate month and year
    if month < 1 or month > 12:
        return format_response(
            success=False,
            message="Invalid month. Must be between 1 and 12",
            status_code=400
        )
    
    if year < 2020 or year > date.today().year + 1:
        return format_response(
            success=False,
            message="Invalid year",
            status_code=400
        )
    
    # Calculate month date range
    start_of_month = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end_of_month = date(year, month, last_day)
    
    # Determine target users based on role and permissions
    target_users = []
    
    if user_id:
        # Specific user requested
        user = User.find_by_id(user_id)
        if not user:
            return format_response(
                success=False,
                message="User not found",
                status_code=404
            )
        
        # Check permissions
        can_view = False
        if current_user.role == 'Admin':
            can_view = True
        elif current_user.role in ['Masool', 'Sheikh'] and User.is_in_hierarchy(user._id, current_user._id):
            can_view = True
        
        if not can_view:
            return format_response(
                success=False,
                message="Insufficient permissions to view this user's report",
                status_code=403
            )
        
        target_users = [user]
    
    else:
        # Get users based on role hierarchy
        if current_user.role == 'Admin':
            target_users = User.find_by_role('Saalik')
        elif current_user.role == 'Sheikh':
            target_users = User.find_by_hierarchy(current_user._id, role_filter='Saalik')
        elif current_user.role == 'Masool':
            target_users = User.find_by_murabi_hierarchy(current_user._id, role_filter='Saalik')
    
    # Generate monthly aggregation
    monthly_stats = {
        'total_users': len(target_users),
        'active_users': 0,
        'total_entries': 0,
        'average_completion_rate': 0,
        'total_violations': 0,
        'weekly_breakdown': [],
        'level_distribution': {},
        'murabi_performance': {}
    }
    
    user_reports = []
    
    # Calculate weekly breakdown for the month
    current_week_start = start_of_month
    week_number = 1
    
    while current_week_start <= end_of_month:
        week_end = min(current_week_start + timedelta(days=6), end_of_month)
        
        week_stats = {
            'week_number': week_number,
            'start_date': current_week_start.isoformat(),
            'end_date': week_end.isoformat(),
            'active_users': 0,
            'total_entries': 0,
            'completion_rate': 0
        }
        
        week_completion_rates = []
        
        for user in target_users:
            entries = Entry.find_by_user(user._id, start_date=current_week_start, end_date=week_end)
            if entries:
                week_stats['active_users'] += 1
                week_stats['total_entries'] += len(entries)
                
                # Calculate completion rate for this week
                summary = generate_weekly_summary(user, current_week_start, week_end)
                week_completion_rates.append(summary.get('zikr_completion_percentage', 0))
        
        if week_completion_rates:
            week_stats['completion_rate'] = sum(week_completion_rates) / len(week_completion_rates)
        
        monthly_stats['weekly_breakdown'].append(week_stats)
        
        current_week_start = week_end + timedelta(days=1)
        week_number += 1
    
    # Generate detailed user reports
    for user in target_users:
        entries = Entry.find_by_user(user._id, start_date=start_of_month, end_date=end_of_month)
        
        # Calculate monthly summary
        summary = generate_weekly_summary(user, start_of_month, end_of_month)
        cycle_progress = calculate_cycle_progress(user)
        
        user_report = {
            'user_id': str(user._id),
            'name': user.name,
            'phone': user.phone,
            'level': user.level,
            'murabi_name': None,
            'total_entries': len(entries),
            'days_submitted': summary.get('days_with_entries', 0),
            'completion_rate': summary.get('zikr_completion_percentage', 0),
            'cycle_progress': cycle_progress,
            'violations_count': len(summary.get('violations', [])),
            'consistency_score': 0  # Days submitted / Total days in month
        }
        
        # Calculate consistency score
        total_days = (end_of_month - start_of_month).days + 1
        user_report['consistency_score'] = (user_report['days_submitted'] / total_days) * 100
        
        # Get Murabi name
        if user.murabi_id:
            murabi = User.find_by_id(user.murabi_id)
            if murabi:
                user_report['murabi_name'] = murabi.name
                
                # Update Murabi performance stats
                murabi_key = str(user.murabi_id)
                if murabi_key not in monthly_stats['murabi_performance']:
                    monthly_stats['murabi_performance'][murabi_key] = {
                        'murabi_name': murabi.name,
                        'total_saalik': 0,
                        'active_saalik': 0,
                        'average_completion': 0,
                        'total_violations': 0
                    }
                
                monthly_stats['murabi_performance'][murabi_key]['total_saalik'] += 1
                if len(entries) > 0:
                    monthly_stats['murabi_performance'][murabi_key]['active_saalik'] += 1
                monthly_stats['murabi_performance'][murabi_key]['total_violations'] += user_report['violations_count']
        
        user_reports.append(user_report)
        
        # Update overall stats
        if len(entries) > 0:
            monthly_stats['active_users'] += 1
        monthly_stats['total_entries'] += len(entries)
        monthly_stats['total_violations'] += user_report['violations_count']
        
        # Update level distribution
        level_key = f"Level {user.level}"
        if level_key not in monthly_stats['level_distribution']:
            monthly_stats['level_distribution'][level_key] = {
                'count': 0,
                'average_completion': 0,
                'total_completion': 0
            }
        monthly_stats['level_distribution'][level_key]['count'] += 1
        monthly_stats['level_distribution'][level_key]['total_completion'] += user_report['completion_rate']
    
    # Calculate averages
    if monthly_stats['total_users'] > 0:
        total_completion = sum(report['completion_rate'] for report in user_reports)
        monthly_stats['average_completion_rate'] = total_completion / monthly_stats['total_users']
    
    # Calculate level distribution averages
    for level_data in monthly_stats['level_distribution'].values():
        if level_data['count'] > 0:
            level_data['average_completion'] = level_data['total_completion'] / level_data['count']
        level_data.pop('total_completion')  # Remove temporary field
    
    # Calculate Murabi performance averages
    for murabi_data in monthly_stats['murabi_performance'].values():
        if murabi_data['total_saalik'] > 0:
            completion_sum = sum(
                report['completion_rate'] 
                for report in user_reports 
                if report['murabi_name'] == murabi_data['murabi_name']
            )
            murabi_data['average_completion'] = completion_sum / murabi_data['total_saalik']
    
    return format_response(
        success=True,
        message="Monthly report generated successfully",
        data={
            'period': {
                'type': 'monthly',
                'year': year,
                'month': month,
                'month_name': calendar.month_name[month],
                'start_date': start_of_month.isoformat(),
                'end_date': end_of_month.isoformat()
            },
            'monthly_stats': monthly_stats,
            'user_reports': user_reports,
            'generated_by': {
                'user_id': str(current_user._id),
                'name': current_user.name,
                'role': current_user.role
            },
            'generated_at': datetime.utcnow().isoformat()
        }
    )

@reports_bp.route('/custom', methods=['GET'])
@jwt_required_custom
@role_required('Murabi', 'Masool', 'Sheikh', 'Admin')
@rate_limit(max_requests=20, window_minutes=60)
def custom_report():
    """Generate custom period report"""
    current_user = g.current_user
    
    # Get query parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    user_id = request.args.get('user_id')
    group_by = request.args.get('group_by', 'user')  # user, murabi, level
    
    if not start_date or not end_date:
        return format_response(
            success=False,
            message="start_date and end_date are required",
            status_code=400
        )
    
    # Parse dates
    start_date_obj = parse_date_from_string(start_date)
    end_date_obj = parse_date_from_string(end_date)
    
    if not start_date_obj or not end_date_obj:
        return format_response(
            success=False,
            message="Invalid date format. Use YYYY-MM-DD",
            status_code=400
        )
    
    # Validate date range
    is_valid, error = validate_date_range(start_date_obj, end_date_obj)
    if not is_valid:
        return format_response(success=False, message=error, status_code=400)
    
    # Check if date range is not too large (max 6 months)
    if (end_date_obj - start_date_obj).days > 180:
        return format_response(
            success=False,
            message="Date range cannot exceed 6 months",
            status_code=400
        )
    
    # Determine target users
    target_users = []
    
    if user_id:
        user = User.find_by_id(user_id)
        if not user:
            return format_response(
                success=False,
                message="User not found",
                status_code=404
            )
        
        # Check permissions
        can_view = False
        if current_user.role == 'Admin':
            can_view = True
        elif current_user.role == 'Murabi' and str(user.murabi_id) == str(current_user._id):
            can_view = True
        elif current_user.role in ['Masool', 'Sheikh'] and User.is_in_hierarchy(user._id, current_user._id):
            can_view = True
        
        if not can_view:
            return format_response(
                success=False,
                message="Insufficient permissions to view this user's report",
                status_code=403
            )
        
        target_users = [user]
    
    else:
        # Get users based on role hierarchy
        if current_user.role == 'Admin':
            target_users = User.find_by_role('Saalik')
        elif current_user.role == 'Sheikh':
            target_users = User.find_by_hierarchy(current_user._id, role_filter='Saalik')
        elif current_user.role == 'Masool':
            target_users = User.find_by_murabi_hierarchy(current_user._id, role_filter='Saalik')
        elif current_user.role == 'Murabi':
            target_users = User.find_by_murabi_id(current_user._id)
    
    # Generate report data
    report_data = {
        'period': {
            'type': 'custom',
            'start_date': start_date_obj.isoformat(),
            'end_date': end_date_obj.isoformat(),
            'duration_days': (end_date_obj - start_date_obj).days + 1
        },
        'summary': {
            'total_users': len(target_users),
            'active_users': 0,
            'total_entries': 0,
            'average_completion_rate': 0,
            'total_violations': 0
        },
        'grouped_data': {},
        'user_details': []
    }
    
    # Collect data for each user
    all_completion_rates = []
    
    for user in target_users:
        entries = Entry.find_by_user(user._id, start_date=start_date_obj, end_date=end_date_obj)
        summary = generate_weekly_summary(user, start_date_obj, end_date_obj)
        
        user_data = {
            'user_id': str(user._id),
            'name': user.name,
            'phone': user.phone,
            'level': user.level,
            'murabi_name': None,
            'entries_count': len(entries),
            'completion_rate': summary.get('zikr_completion_percentage', 0),
            'violations_count': len(summary.get('violations', [])),
            'days_submitted': summary.get('days_with_entries', 0)
        }
        
        # Get Murabi name
        if user.murabi_id:
            murabi = User.find_by_id(user.murabi_id)
            if murabi:
                user_data['murabi_name'] = murabi.name
        
        report_data['user_details'].append(user_data)
        
        # Update summary stats
        if len(entries) > 0:
            report_data['summary']['active_users'] += 1
        report_data['summary']['total_entries'] += len(entries)
        report_data['summary']['total_violations'] += user_data['violations_count']
        all_completion_rates.append(user_data['completion_rate'])
        
        # Group data based on group_by parameter
        if group_by == 'murabi':
            group_key = user_data['murabi_name'] or 'Unassigned'
        elif group_by == 'level':
            group_key = f"Level {user.level}"
        else:  # group_by == 'user'
            group_key = user.name
        
        if group_key not in report_data['grouped_data']:
            report_data['grouped_data'][group_key] = {
                'users_count': 0,
                'total_entries': 0,
                'average_completion': 0,
                'total_violations': 0,
                'completion_rates': []
            }
        
        group_data = report_data['grouped_data'][group_key]
        group_data['users_count'] += 1
        group_data['total_entries'] += len(entries)
        group_data['total_violations'] += user_data['violations_count']
        group_data['completion_rates'].append(user_data['completion_rate'])
    
    # Calculate averages
    if all_completion_rates:
        report_data['summary']['average_completion_rate'] = sum(all_completion_rates) / len(all_completion_rates)
    
    # Calculate group averages
    for group_data in report_data['grouped_data'].values():
        if group_data['completion_rates']:
            group_data['average_completion'] = sum(group_data['completion_rates']) / len(group_data['completion_rates'])
        group_data.pop('completion_rates')  # Remove temporary field
    
    return format_response(
        success=True,
        message="Custom report generated successfully",
        data={
            **report_data,
            'generated_by': {
                'user_id': str(current_user._id),
                'name': current_user.name,
                'role': current_user.role
            },
            'generated_at': datetime.utcnow().isoformat()
        }
    )

@reports_bp.route('/analytics', methods=['GET'])
@jwt_required_custom
@role_required('Sheikh', 'Admin')
@rate_limit(max_requests=10, window_minutes=60)
def analytics_report():
    """Generate advanced analytics report (Sheikh and Admin only)"""
    current_user = g.current_user
    
    # Get query parameters
    period = request.args.get('period', 'month')  # week, month, quarter, year
    
    # Calculate date range based on period
    today = date.today()
    
    if period == 'week':
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
    elif period == 'month':
        start_date = today.replace(day=1)
        last_day = calendar.monthrange(today.year, today.month)[1]
        end_date = today.replace(day=last_day)
    elif period == 'quarter':
        quarter = (today.month - 1) // 3 + 1
        start_month = (quarter - 1) * 3 + 1
        start_date = date(today.year, start_month, 1)
        end_month = quarter * 3
        last_day = calendar.monthrange(today.year, end_month)[1]
        end_date = date(today.year, end_month, last_day)
    elif period == 'year':
        start_date = date(today.year, 1, 1)
        end_date = date(today.year, 12, 31)
    else:
        return format_response(
            success=False,
            message="Invalid period. Use 'week', 'month', 'quarter', or 'year'",
            status_code=400
        )
    
    # Get all users in hierarchy
    if current_user.role == 'Admin':
        all_users = User.find_all()
        all_saalik = User.find_by_role('Saalik')
    else:  # Sheikh
        all_users = User.find_by_hierarchy(current_user._id)
        all_saalik = User.find_by_hierarchy(current_user._id, role_filter='Saalik')
    
    # Generate comprehensive analytics
    analytics = {
        'period': {
            'type': period,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        },
        'user_statistics': {
            'total_users': len(all_users),
            'active_saalik': 0,
            'inactive_saalik': 0,
            'role_distribution': {},
            'level_distribution': {}
        },
        'performance_metrics': {
            'overall_completion_rate': 0,
            'top_performers': [],
            'bottom_performers': [],
            'improvement_trends': []
        },
        'murabi_effectiveness': {},
        'system_health': {
            'total_entries': 0,
            'daily_average': 0,
            'violation_rate': 0,
            'cycle_restart_rate': 0
        }
    }
    
    # Calculate user statistics
    role_counts = {}
    level_counts = {}
    all_completion_rates = []
    
    for user in all_users:
        # Role distribution
        role_counts[user.role] = role_counts.get(user.role, 0) + 1
        
        if user.role == 'Saalik':
            # Level distribution
            level_key = f"Level {user.level}"
            level_counts[level_key] = level_counts.get(level_key, 0) + 1
            
            # Get user's entries for the period
            entries = Entry.find_by_user(user._id, start_date=start_date, end_date=end_date)
            summary = generate_weekly_summary(user, start_date, end_date)
            completion_rate = summary.get('zikr_completion_percentage', 0)
            
            if len(entries) > 0:
                analytics['user_statistics']['active_saalik'] += 1
                all_completion_rates.append({
                    'user_id': str(user._id),
                    'name': user.name,
                    'completion_rate': completion_rate,
                    'entries_count': len(entries),
                    'violations': len(summary.get('violations', []))
                })
            else:
                analytics['user_statistics']['inactive_saalik'] += 1
            
            analytics['system_health']['total_entries'] += len(entries)
    
    analytics['user_statistics']['role_distribution'] = role_counts
    analytics['user_statistics']['level_distribution'] = level_counts
    
    # Calculate performance metrics
    if all_completion_rates:
        total_completion = sum(user['completion_rate'] for user in all_completion_rates)
        analytics['performance_metrics']['overall_completion_rate'] = total_completion / len(all_completion_rates)
        
        # Sort by completion rate
        sorted_performers = sorted(all_completion_rates, key=lambda x: x['completion_rate'], reverse=True)
        
        # Top and bottom performers (top/bottom 10 or 20% whichever is smaller)
        top_count = min(10, max(1, len(sorted_performers) // 5))
        analytics['performance_metrics']['top_performers'] = sorted_performers[:top_count]
        analytics['performance_metrics']['bottom_performers'] = sorted_performers[-top_count:]
    
    # Calculate system health metrics
    total_days = (end_date - start_date).days + 1
    if total_days > 0:
        analytics['system_health']['daily_average'] = analytics['system_health']['total_entries'] / total_days
    
    # Calculate violation and cycle restart rates
    total_violations = sum(user['violations'] for user in all_completion_rates)
    if analytics['system_health']['total_entries'] > 0:
        analytics['system_health']['violation_rate'] = (total_violations / analytics['system_health']['total_entries']) * 100
    
    # Calculate Murabi effectiveness
    murabi_users = User.find_by_role('Murabi')
    for murabi in murabi_users:
        if current_user.role != 'Admin' and not User.is_in_hierarchy(murabi._id, current_user._id):
            continue
        
        assigned_saalik = User.find_by_murabi_id(murabi._id)
        murabi_stats = {
            'murabi_name': murabi.name,
            'total_assigned': len(assigned_saalik),
            'active_saalik': 0,
            'average_completion': 0,
            'total_violations': 0
        }
        
        saalik_completions = []
        for saalik in assigned_saalik:
            entries = Entry.find_by_user(saalik._id, start_date=start_date, end_date=end_date)
            if entries:
                murabi_stats['active_saalik'] += 1
                summary = generate_weekly_summary(saalik, start_date, end_date)
                saalik_completions.append(summary.get('zikr_completion_percentage', 0))
                murabi_stats['total_violations'] += len(summary.get('violations', []))
        
        if saalik_completions:
            murabi_stats['average_completion'] = sum(saalik_completions) / len(saalik_completions)
        
        analytics['murabi_effectiveness'][str(murabi._id)] = murabi_stats
    
    return format_response(
        success=True,
        message="Analytics report generated successfully",
        data={
            **analytics,
            'generated_by': {
                'user_id': str(current_user._id),
                'name': current_user.name,
                'role': current_user.role
            },
            'generated_at': datetime.utcnow().isoformat()
        }
    )