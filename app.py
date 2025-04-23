import os
import logging
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
import oss2
import datetime
import json
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('data/sync.log')
    ]
)
logger = logging.getLogger(__name__)

# 创建Flask应用
app = Flask(__name__, static_folder='frontend/dist')
CORS(app)

# 确保数据目录存在
os.makedirs('data', exist_ok=True)
logs_file = 'data/logs.json'
config_file = 'data/config.json'

# 如果日志文件不存在，创建一个空的
if not os.path.exists(logs_file):
    with open(logs_file, 'w') as f:
        json.dump([], f)

# 如果配置文件不存在，创建默认配置
if not os.path.exists(config_file):
    default_config = {
        'schedule': {
            'enabled': False,
            'interval': 3600  # 默认每小时同步一次
        },
        'ignore_patterns': ['.git/', '.DS_Store', '*.tmp'],
        'sync_status': 'stopped'
    }
    with open(config_file, 'w') as f:
        json.dump(default_config, f)

# 读取OSS配置
oss_access_key_id = os.environ.get('OSS_ACCESS_KEY_ID')
oss_access_key_secret = os.environ.get('OSS_ACCESS_KEY_SECRET')
oss_bucket_name = os.environ.get('OSS_BUCKET')
oss_endpoint = os.environ.get('OSS_ENDPOINT')

# 初始化OSS客户端
def get_oss_client():
    if not all([oss_access_key_id, oss_access_key_secret, oss_bucket_name, oss_endpoint]):
        logger.error("OSS配置不完整")
        return None, None
    
    auth = oss2.Auth(oss_access_key_id, oss_access_key_secret)
    bucket = oss2.Bucket(auth, oss_endpoint, oss_bucket_name)
    return auth, bucket

# 添加日志记录
def add_log(message, level='info'):
    log_entry = {
        'timestamp': datetime.datetime.now().isoformat(),
        'message': message,
        'level': level
    }
    
    logs = []
    if os.path.exists(logs_file):
        with open(logs_file, 'r') as f:
            try:
                logs = json.load(f)
            except json.JSONDecodeError:
                logs = []
    
    logs.insert(0, log_entry)
    logs = logs[:100]  # 保留最近的100条日志
    
    with open(logs_file, 'w') as f:
        json.dump(logs, f)
    
    if level == 'error':
        logger.error(message)
    else:
        logger.info(message)

# 同步文件到OSS
def sync_to_oss():
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        if config.get('sync_status') != 'running':
            return
        
        auth, bucket = get_oss_client()
        if not bucket:
            add_log("OSS客户端初始化失败", "error")
            return
        
        host_dir = '/host_files'
        ignore_patterns = config.get('ignore_patterns', [])
        
        add_log(f"开始同步: {host_dir} -> OSS")
        
        # 获取OSS上已有的文件列表
        existing_objects = {}
        for obj in oss2.ObjectIterator(bucket):
            existing_objects[obj.key] = obj.etag
        
        # 同步文件
        for root, dirs, files in os.walk(host_dir):
            # 检查是否需要忽略当前目录
            if any(Path(root).match(pattern) for pattern in ignore_patterns if '*' not in pattern):
                continue
                
            for file in files:
                # 检查是否需要忽略当前文件
                if any(Path(file).match(pattern) for pattern in ignore_patterns if '*' in pattern):
                    continue
                
                local_path = os.path.join(root, file)
                # 计算相对路径作为OSS的key
                oss_key = os.path.relpath(local_path, host_dir).replace('\\', '/')
                
                # 检查文件是否已经存在于OSS
                file_stat = os.stat(local_path)
                file_size = file_stat.st_size
                file_mtime = file_stat.st_mtime
                
                should_upload = True
                if oss_key in existing_objects:
                    # TODO: 实现更精确的文件比较方式
                    # 这里简单地比较文件大小和修改时间
                    head = bucket.head_object(oss_key)
                    if head.content_length == file_size:
                        should_upload = False
                        add_log(f"跳过相同文件: {oss_key}")
                
                if should_upload:
                    with open(local_path, 'rb') as f:
                        bucket.put_object(oss_key, f)
                    add_log(f"上传文件: {oss_key}")
        
        add_log("同步完成")
    except Exception as e:
        add_log(f"同步过程出错: {str(e)}", "error")

# 创建定时任务调度器
scheduler = BackgroundScheduler()
scheduler.start()

# 根据配置设置定时任务
def setup_scheduler():
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        # 删除旧的定时任务
        scheduler.remove_all_jobs()
        
        if config.get('schedule', {}).get('enabled', False):
            interval = config.get('schedule', {}).get('interval', 3600)
            scheduler.add_job(
                sync_to_oss, 
                'interval', 
                seconds=interval,
                id='sync_job'
            )
            add_log(f"已设置定时同步任务，间隔 {interval} 秒")
        else:
            add_log("定时同步任务已禁用")
    except Exception as e:
        add_log(f"设置定时任务失败: {str(e)}", "error")

# 启动时设置定时任务
setup_scheduler()

# 路由：测试OSS连接
@app.route('/api/test-connection', methods=['GET'])
def test_connection():
    try:
        auth, bucket = get_oss_client()
        if not bucket:
            return jsonify({'success': False, 'message': 'OSS配置不完整'}), 400
        
        # 尝试列出Bucket
        bucket.list_objects(max_keys=1)
        add_log("OSS连接测试成功")
        return jsonify({'success': True, 'message': 'OSS连接成功'})
    except Exception as e:
        add_log(f"OSS连接测试失败: {str(e)}", "error")
        return jsonify({'success': False, 'message': str(e)}), 500

# 路由：获取日志
@app.route('/api/logs', methods=['GET'])
def get_logs():
    try:
        with open(logs_file, 'r') as f:
            logs = json.load(f)
        return jsonify(logs)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 路由：获取配置
@app.route('/api/config', methods=['GET'])
def get_config():
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        return jsonify(config)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 路由：更新配置
@app.route('/api/config', methods=['POST'])
def update_config():
    try:
        new_config = request.json
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        # 更新配置
        if 'schedule' in new_config:
            config['schedule'] = new_config['schedule']
        if 'ignore_patterns' in new_config:
            config['ignore_patterns'] = new_config['ignore_patterns']
        
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        # 重新设置调度器
        setup_scheduler()
        
        add_log("配置已更新")
        return jsonify({'success': True})
    except Exception as e:
        add_log(f"更新配置失败: {str(e)}", "error")
        return jsonify({'success': False, 'error': str(e)}), 500

# 路由：开始同步
@app.route('/api/sync/start', methods=['POST'])
def start_sync():
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        config['sync_status'] = 'running'
        
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        add_log("同步任务已开始")
        # 立即开始一次同步
        sync_to_oss()
        return jsonify({'success': True})
    except Exception as e:
        add_log(f"开始同步失败: {str(e)}", "error")
        return jsonify({'success': False, 'error': str(e)}), 500

# 路由：停止同步
@app.route('/api/sync/stop', methods=['POST'])
def stop_sync():
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        config['sync_status'] = 'stopped'
        
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        add_log("同步任务已停止")
        return jsonify({'success': True})
    except Exception as e:
        add_log(f"停止同步失败: {str(e)}", "error")
        return jsonify({'success': False, 'error': str(e)}), 500

# 路由：查看宿主机文件
@app.route('/api/files', methods=['GET'])
def list_files():
    try:
        path = request.args.get('path', '/')
        full_path = os.path.normpath(os.path.join('/host_files', path.lstrip('/')))
        
        # 安全检查，确保路径在/host_files下
        if not full_path.startswith('/host_files'):
            return jsonify({'error': '无效的路径'}), 400
        
        if not os.path.exists(full_path):
            return jsonify({'error': '路径不存在'}), 404
        
        if os.path.isfile(full_path):
            # 如果是文件，返回文件信息
            stat = os.stat(full_path)
            return jsonify({
                'type': 'file',
                'name': os.path.basename(full_path),
                'size': stat.st_size,
                'modified': datetime.datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
        
        # 如果是目录，返回目录内容
        items = []
        for item in os.listdir(full_path):
            item_path = os.path.join(full_path, item)
            stat = os.stat(item_path)
            items.append({
                'type': 'directory' if os.path.isdir(item_path) else 'file',
                'name': item,
                'size': stat.st_size,
                'modified': datetime.datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
        
        return jsonify({
            'type': 'directory',
            'path': path,
            'items': items
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 路由：前端应用
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=2003) 