import os
import logging
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
import oss2
import datetime
import json
import threading
import time
from pathlib import Path
import queue
import io
import math

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
status_file = 'data/status.json'

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

# 如果状态文件不存在，创建默认状态
if not os.path.exists(status_file):
    default_status = {
        'is_syncing': False,
        'progress': {
            'total_files': 0,
            'processed_files': 0,
            'current_file': '',
            'start_time': None,
            'end_time': None
        },
        'network': {
            'speed': 0,        # 当前速度，单位：字节/秒
            'avg_speed': 0,    # 平均速度，单位：字节/秒
            'total_bytes': 0,  # 已传输总字节数
            'last_update': None # 最后更新时间
        }
    }
    with open(status_file, 'w') as f:
        json.dump(default_status, f)

# 读取OSS配置
oss_access_key_id = os.environ.get('OSS_ACCESS_KEY_ID')
oss_access_key_secret = os.environ.get('OSS_ACCESS_KEY_SECRET')
oss_bucket_name = os.environ.get('OSS_BUCKET')
oss_endpoint = os.environ.get('OSS_ENDPOINT')

# 同步任务队列和锁
sync_queue = queue.Queue()
sync_lock = threading.Lock()

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

# 更新同步状态
def update_sync_status(is_syncing=None, total_files=None, processed_files=None, current_file=None, 
                      network_speed=None, total_bytes=None):
    with sync_lock:
        status = {}
        if os.path.exists(status_file):
            with open(status_file, 'r') as f:
                try:
                    status = json.load(f)
                except json.JSONDecodeError:
                    status = {'is_syncing': False, 'progress': {}, 'network': {}}
        
        if 'progress' not in status:
            status['progress'] = {}
            
        if 'network' not in status:
            status['network'] = {
                'speed': 0,
                'avg_speed': 0,
                'total_bytes': 0,
                'last_update': None
            }
        
        if is_syncing is not None:
            status['is_syncing'] = is_syncing
            
            # 当开始或结束同步时，更新时间戳
            if is_syncing:
                status['progress']['start_time'] = datetime.datetime.now().isoformat()
                status['progress']['end_time'] = None
                # 重置网络统计
                status['network']['speed'] = 0
                status['network']['avg_speed'] = 0
                status['network']['total_bytes'] = 0
                status['network']['last_update'] = datetime.datetime.now().isoformat()
            elif 'progress' in status and status['progress'].get('start_time') and not status['progress'].get('end_time'):
                status['progress']['end_time'] = datetime.datetime.now().isoformat()
        
        if total_files is not None:
            status['progress']['total_files'] = total_files
        
        if processed_files is not None:
            status['progress']['processed_files'] = processed_files
        
        if current_file is not None:
            status['progress']['current_file'] = current_file
            
        # 更新网络状态
        if network_speed is not None:
            status['network']['speed'] = network_speed
            
            # 更新最后更新时间
            now = datetime.datetime.now().isoformat()
            status['network']['last_update'] = now
            
        if total_bytes is not None:
            # 计算传输总量
            status['network']['total_bytes'] = total_bytes
            
            # 计算平均速度
            if status['progress'].get('start_time'):
                start_time = datetime.datetime.fromisoformat(status['progress']['start_time'])
                now = datetime.datetime.now()
                elapsed_seconds = (now - start_time).total_seconds()
                if elapsed_seconds > 0:
                    status['network']['avg_speed'] = total_bytes / elapsed_seconds
        
        with open(status_file, 'w') as f:
            json.dump(status, f)

# 格式化大小
def format_size(bytes, suffix="B"):
    if bytes == 0:
        return "0 " + suffix
    size_name = ("", "K", "M", "G", "T", "P", "E", "Z", "Y")
    i = int(math.floor(math.log(bytes, 1024)))
    p = math.pow(1024, i)
    s = round(bytes / p, 2)
    return f"{s} {size_name[i]}{suffix}"

# 计算文件总数
def count_files(directory, ignore_patterns):
    count = 0
    for root, dirs, files in os.walk(directory):
        # 检查是否需要忽略当前目录
        if any(Path(root).match(pattern) for pattern in ignore_patterns if '*' not in pattern):
            continue
            
        for file in files:
            # 检查是否需要忽略当前文件
            if any(Path(file).match(pattern) for pattern in ignore_patterns if '*' in pattern):
                continue
            count += 1
    return count

# 带宽监控流
class BandwidthMonitoringStream(io.IOBase):
    def __init__(self, original_stream, file_size, file_path):
        self.original_stream = original_stream
        self.bytes_read = 0
        self.last_update_time = time.time()
        self.last_bytes_read = 0
        self.speed = 0
        self.file_size = file_size
        self.file_path = file_path
        
    def read(self, size=-1):
        data = self.original_stream.read(size)
        self.bytes_read += len(data)
        
        # 每0.5秒更新一次速度
        current_time = time.time()
        if current_time - self.last_update_time >= 0.5:
            time_diff = current_time - self.last_update_time
            bytes_diff = self.bytes_read - self.last_bytes_read
            
            if time_diff > 0:
                self.speed = bytes_diff / time_diff
                
                # 获取当前的总传输字节数
                with sync_lock:
                    try:
                        with open(status_file, 'r') as f:
                            status = json.load(f)
                        total_bytes = status.get('network', {}).get('total_bytes', 0)
                    except (json.JSONDecodeError, FileNotFoundError):
                        total_bytes = 0
                
                # 更新网速和总传输量
                update_sync_status(
                    network_speed=self.speed, 
                    total_bytes=total_bytes + bytes_diff
                )
                
                # 记录日志
                formatted_speed = format_size(self.speed) + "/s"
                progress_percent = int(self.bytes_read / self.file_size * 100) if self.file_size > 0 else 0
                logger.info(f"上传 {self.file_path}: {progress_percent}% 完成，当前速度: {formatted_speed}")
            
            self.last_update_time = current_time
            self.last_bytes_read = self.bytes_read
            
        return data
    
    # 添加必要的方法以满足文件对象接口
    def seekable(self):
        return False
    
    def readable(self):
        return True
    
    def writable(self):
        return False
        
    def __getattr__(self, attr):
        return getattr(self.original_stream, attr)

# 同步文件到OSS（后台线程函数）
def sync_worker():
    while True:
        try:
            # 从队列获取任务，如果没有任务则阻塞等待
            task = sync_queue.get(block=True)
            
            # 检查是否是退出信号
            if task == "EXIT":
                break
            
            # 开始同步任务
            add_log("开始同步任务")
            sync_to_oss_task()
            
        except Exception as e:
            add_log(f"同步任务出错: {str(e)}", "error")
        finally:
            # 标记任务完成
            sync_queue.task_done()

# 同步文件到OSS（具体任务实现）
def sync_to_oss_task():
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        if config.get('sync_status') != 'running':
            return
        
        auth, bucket = get_oss_client()
        if not bucket:
            add_log("OSS客户端初始化失败", "error")
            update_sync_status(is_syncing=False)
            return
        
        host_dir = '/host_files'
        ignore_patterns = config.get('ignore_patterns', [])
        
        add_log(f"开始同步: {host_dir} -> OSS")
        update_sync_status(is_syncing=True)
        
        # 计算文件总数
        total_files = count_files(host_dir, ignore_patterns)
        update_sync_status(total_files=total_files, processed_files=0)
        add_log(f"找到 {total_files} 个文件需要同步")
        
        # 获取OSS上已有的文件列表
        add_log("获取OSS上已有的文件列表")
        existing_objects = {}
        for obj in oss2.ObjectIterator(bucket):
            existing_objects[obj.key] = obj.etag
        
        # 同步文件
        processed_files = 0
        total_bytes_transferred = 0
        
        for root, dirs, files in os.walk(host_dir):
            # 检查是否需要忽略当前目录
            if any(Path(root).match(pattern) for pattern in ignore_patterns if '*' not in pattern):
                continue
                
            for file in files:
                # 检查是否需要忽略当前文件
                if any(Path(file).match(pattern) for pattern in ignore_patterns if '*' in pattern):
                    continue
                
                # 检查同步是否被停止
                with open(config_file, 'r') as f:
                    current_config = json.load(f)
                if current_config.get('sync_status') != 'running':
                    add_log("同步任务被手动停止")
                    update_sync_status(is_syncing=False)
                    return
                
                local_path = os.path.join(root, file)
                # 计算相对路径作为OSS的key
                oss_key = os.path.relpath(local_path, host_dir).replace('\\', '/')
                
                # 更新当前处理的文件
                update_sync_status(current_file=oss_key, processed_files=processed_files)
                
                # 检查文件是否已经存在于OSS
                file_stat = os.stat(local_path)
                file_size = file_stat.st_size
                
                should_upload = True
                if oss_key in existing_objects:
                    try:
                        # 实现更精确的文件比较
                        head = bucket.head_object(oss_key)
                        if head.content_length == file_size:
                            should_upload = False
                            add_log(f"跳过相同文件: {oss_key}")
                    except oss2.exceptions.NoSuchKey:
                        pass  # 文件不存在，需要上传
                
                if should_upload:
                    try:
                        # 使用分片上传来处理大文件
                        if file_size > 10 * 1024 * 1024:  # 超过10MB使用分片上传
                            add_log(f"开始分片上传大文件: {oss_key}")
                            
                            # 初始化分片上传
                            upload_id = bucket.init_multipart_upload(oss_key).upload_id
                            parts = []
                            
                            # 分片大小5MB
                            part_size = 5 * 1024 * 1024
                            num_parts = (file_size + part_size - 1) // part_size
                            
                            with open(local_path, 'rb') as f:
                                for i in range(num_parts):
                                    # 记录开始时间
                                    start_time = time.time()
                                    
                                    # 读取分片数据
                                    data = f.read(part_size)
                                    part_bytes = len(data)
                                    
                                    # 上传分片
                                    result = bucket.upload_part(oss_key, upload_id, i + 1, data)
                                    parts.append(oss2.models.PartInfo(i + 1, result.etag))
                                    
                                    # 记录结束时间并计算速度
                                    end_time = time.time()
                                    elapsed = end_time - start_time
                                    if elapsed > 0:
                                        speed = part_bytes / elapsed
                                        total_bytes_transferred += part_bytes
                                        update_sync_status(
                                            network_speed=speed,
                                            total_bytes=total_bytes_transferred
                                        )
                                        
                                        # 记录日志
                                        formatted_speed = format_size(speed) + "/s"
                                        progress = (i + 1) / num_parts * 100
                                        add_log(f"分片上传 {oss_key} 进度: {progress:.1f}%, 速度: {formatted_speed}")
                                    
                            # 完成分片上传
                            bucket.complete_multipart_upload(oss_key, upload_id, parts)
                            add_log(f"完成分片上传: {oss_key}")
                        else:
                            # 小文件上传 - 使用简单方法而不是带宽监控
                            try:
                                with open(local_path, 'rb') as f:
                                    # 记录开始时间
                                    start_time = time.time()
                                    
                                    # 直接上传文件
                                    bucket.put_object(oss_key, f)
                                    
                                    # 记录结束时间并计算速度
                                    end_time = time.time()
                                    elapsed = end_time - start_time
                                    
                                    if elapsed > 0:
                                        speed = file_size / elapsed
                                        total_bytes_transferred += file_size
                                        update_sync_status(
                                            network_speed=speed,
                                            total_bytes=total_bytes_transferred
                                        )
                                
                                add_log(f"上传文件: {oss_key}")
                            except Exception as e:
                                add_log(f"上传文件 {oss_key} 失败: {str(e)}", "error")
                    except Exception as e:
                        add_log(f"上传文件 {oss_key} 失败: {str(e)}", "error")
                
                processed_files += 1
                update_sync_status(processed_files=processed_files)
        
        # 确保网络统计最终准确
        update_sync_status(
            is_syncing=False,
            processed_files=processed_files,
            total_bytes=total_bytes_transferred
        )
        
        add_log(f"同步完成，共处理 {processed_files} 个文件，传输总量: {format_size(total_bytes_transferred)}")
    except Exception as e:
        add_log(f"同步过程出错: {str(e)}", "error")
        update_sync_status(is_syncing=False)

# 启动同步任务
def start_sync_task():
    try:
        # 将任务添加到队列
        sync_queue.put("SYNC")
    except Exception as e:
        add_log(f"启动同步任务失败: {str(e)}", "error")

# 启动工作线程
sync_thread = threading.Thread(target=sync_worker, daemon=True)
sync_thread.start()

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
                start_sync_task, 
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

# 路由：获取同步状态
@app.route('/api/sync/status', methods=['GET'])
def get_sync_status():
    try:
        with open(status_file, 'r') as f:
            status = json.load(f)
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 路由：开始同步
@app.route('/api/sync/start', methods=['POST'])
def start_sync():
    try:
        # 检查是否已经在同步
        with open(status_file, 'r') as f:
            status = json.load(f)
        
        if status.get('is_syncing'):
            return jsonify({'success': False, 'message': '同步任务已在进行中'}), 400
        
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        config['sync_status'] = 'running'
        
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        add_log("同步任务已开始")
        
        # 启动异步同步任务
        start_sync_task()
        
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

# 路由：重置同步状态
@app.route('/api/sync/reset', methods=['POST'])
def reset_sync_status():
    try:
        # 重置配置文件中的同步状态
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        config['sync_status'] = 'stopped'
        
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        # 重置状态文件
        default_status = {
            'is_syncing': False,
            'progress': {
                'total_files': 0,
                'processed_files': 0,
                'current_file': '',
                'start_time': None,
                'end_time': None
            },
            'network': {
                'speed': 0,
                'avg_speed': 0,
                'total_bytes': 0,
                'last_update': None
            }
        }
        
        with open(status_file, 'w') as f:
            json.dump(default_status, f)
        
        add_log("同步状态已重置")
        return jsonify({'success': True})
    except Exception as e:
        add_log(f"重置同步状态失败: {str(e)}", "error")
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