"""
Mission Control — Flask Blueprint.

Routes:
    GET  /mission-control      Main page (HTML)
    GET  /api/mc/pose          Current robot pose
    GET  /api/mc/path          Trajectory history  (?limit=N)
    GET  /api/mc/status        SLAM adapter status
    POST /api/mc/reset         Reset position tracking
"""

from flask import Blueprint, jsonify, render_template, request

from mission_control.slam_adapter import get_adapter

mc_bp = Blueprint('mission_control', __name__)


@mc_bp.route('/mission-control')
def mission_control_page():
    return render_template('mission_control.html')


@mc_bp.route('/api/mc/pose')
def mc_pose():
    return jsonify(get_adapter().get_current_pose())


@mc_bp.route('/api/mc/path')
def mc_path():
    limit = request.args.get('limit', 500, type=int)
    limit = max(1, min(limit, 2000))
    path = get_adapter().get_path_history()
    return jsonify({'points': path[-limit:], 'total': len(path)})


@mc_bp.route('/api/mc/status')
def mc_status():
    return jsonify(get_adapter().get_slam_status())


@mc_bp.route('/api/mc/reset', methods=['POST'])
def mc_reset():
    get_adapter().reset_path()
    return jsonify({'ok': True, 'message': 'Tracking reset'})
