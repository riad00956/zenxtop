import os
import subprocess
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template_string, request, session, redirect, jsonify
from flask_socketio import SocketIO, emit
import threading
import time

app = Flask(__name__)
app.secret_key = 'cyber_20_un_secret_key_2024'
socketio = SocketIO(app, cors_allowed_origins="*")

# ডাটাবেজ এবং ডিরেক্টরি সেটআপ
DB_PATH = 'cyber20un.db'
CODE_DIR = Path('user_codes')
CODE_DIR.mkdir(exist_ok=True)

# HTML টেমপ্লেট (আপনার মূল HTML)
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Cyber 20 UN | Dual Terminal IDE</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500&family=Poppins:wght@300;400;600;700&display=swap" rel="stylesheet">
    <script src="https://unpkg.com/lucide@latest"></script>
    <style>
        :root {
            --bg: #020617; --purple: #8b5cf6; --blue: #3b82f6; --cyan: #06b6d4;
            --text: #f8fafc; --glass: rgba(15, 23, 42, 0.8); --border: rgba(255, 255, 255, 0.1);
        }
        * { box-sizing: border-box; transition: all 0.3s ease; }
        body {
            margin: 0; font-family: 'Poppins', sans-serif; background: var(--bg);
            color: var(--text); min-height: 100vh; overflow-x: hidden;
            display: flex; flex-direction: column;
        }
        #bgCanvas { position: fixed; top: 0; left: 0; z-index: -1; }
        .container { width: 100%; padding: 15px; margin-top: 10px; position: relative; z-index: 1; }
        
        .header { 
            display: flex; justify-content: space-between; align-items: center; 
            background: var(--glass); padding: 12px 20px; border-radius: 20px;
            border: 1px solid var(--border); margin-bottom: 20px;
        }
        .logo-text { font-size: 18px; font-weight: 800; background: linear-gradient(to right, var(--purple), var(--cyan)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }

        .card { background: var(--glass); backdrop-filter: blur(15px); border: 1px solid var(--border); border-radius: 24px; padding: 20px; margin-bottom: 20px; }
        
        textarea {
            background: rgba(0, 0, 0, 0.4); border: 1px solid var(--border); color: #10b981; padding: 15px; border-radius: 15px;
            width: 100%; font-family: 'Fira Code', monospace; font-size: 13px; height: 200px; outline: none; margin-top: 10px;
        }

        /* Terminal Styles */
        .terminal-container { display: flex; flex-direction: column; gap: 15px; }
        .terminal-box {
            background: #000; color: #a5f3fc; height: 160px; overflow-y: auto; padding: 12px; border-radius: 15px;
            font-family: 'Fira Code', monospace; font-size: 11px; border: 1px solid var(--border); line-height: 1.4;
        }
        .term-lib { border-color: var(--purple); }
        .term-out { border-color: var(--cyan); }
        
        .term-label { font-size: 12px; font-weight: 600; margin-bottom: 5px; display: flex; align-items: center; gap: 6px; }

        .cmd-input-group { display: flex; gap: 8px; margin-top: 10px; }
        input[type="text"] { background: rgba(0, 0, 0, 0.3); border: 1px solid var(--border); color: var(--text); padding: 10px; border-radius: 10px; flex-grow: 1; font-size: 13px; outline: none; }
        .btn { background: linear-gradient(45deg, var(--purple), var(--blue)); color: white; border: none; padding: 10px 18px; border-radius: 10px; font-weight: 700; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 6px; }
        .btn-play { width: 100%; margin-top: 10px; }

        .log-success { color: #10b981; }
        .log-error { color: #ef4444; }
        .spin { animation: spin 1s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
        
        /* Login Form */
        .login-form {
            max-width: 400px;
            margin: 100px auto;
            padding: 30px;
            background: var(--glass);
            border-radius: 20px;
            text-align: center;
        }
        .login-form input {
            width: 100%;
            margin: 10px 0;
            padding: 12px;
            border-radius: 10px;
            background: rgba(0,0,0,0.3);
            border: 1px solid var(--border);
            color: var(--text);
        }
        .login-btn {
            width: 100%;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <canvas id="bgCanvas"></canvas>
    <div class="container">
        <header class="header">
            <div style="display: flex; align-items: center; gap: 8px;">
                <i data-lucide="zap" fill="var(--cyan)" color="var(--cyan)" size="20"></i>
                <span class="logo-text">Cyber 20 UN</span>
            </div>
            {% if user_id %}
            <button onclick="location.href='/logout'" style="background:none; border:none; color:#ef4444;"><i data-lucide="log-out"></i></button>
            {% endif %}
        </header>

        {% if not user_id %}
        <!-- Login Form -->
        <div class="login-form">
            <h2 style="margin-bottom: 20px;">Welcome to Cyber 20 UN IDE</h2>
            <p style="opacity: 0.8; margin-bottom: 30px;">Enter your username to start coding</p>
            <form method="POST" action="/login">
                <input type="text" name="username" placeholder="Choose a username" required>
                <input type="text" name="project_name" placeholder="Project name (optional)" value="my_project">
                <button type="submit" class="btn login-btn">Start Coding <i data-lucide="arrow-right"></i></button>
            </form>
            <p style="margin-top: 20px; font-size: 12px; opacity: 0.6;">
                No password needed • All data saved locally • Share your project link
            </p>
        </div>
        {% else %}
        <!-- Main IDE Content -->
        <main>
            <div class="card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <i data-lucide="file-code" size="18" color="var(--purple)"></i>
                        <input type="text" id="filename" value="{{ default_file }}" style="border:none; background:none; color:white; width:80px; font-weight:600;">
                    </div>
                    <div style="font-size: 12px; opacity: 0.7;">
                        Project: <strong>{{ session.get('project_name', 'default') }}</strong>
                    </div>
                </div>
                <textarea id="code" placeholder="# Write code here...">{{ default_content }}</textarea>
                <button onclick="runCode(this)" class="btn btn-play"><i data-lucide="play"></i> Run Code</button>
            </div>

            <div class="terminal-container">
                <div class="card" style="margin-bottom: 0;">
                    <div class="term-label" style="color: var(--purple);"><i data-lucide="package"></i> Library Installer Logs</div>
                    <div id="lib-terminal" class="terminal-box term-lib">
                        <div style="opacity:0.5;">[WAITING] Install libraries via command...</div>
                    </div>
                    <div class="cmd-input-group">
                        <input type="text" id="cmd" placeholder="pip install ...">
                        <button onclick="sendCmd()" class="btn"><i data-lucide="download" size="16"></i></button>
                    </div>
                </div>

                <div class="card">
                    <div class="term-label" style="color: var(--cyan);"><i data-lucide="terminal"></i> Execution Output</div>
                    <div id="out-terminal" class="terminal-box term-out">
                        <div style="opacity:0.5;">[READY] Program output will appear here...</div>
                    </div>
                </div>
            </div>
        </main>
        {% endif %}
    </div>

    <script>
        lucide.createIcons();
        const socket = io();

        // Background
        const canvas = document.getElementById('bgCanvas');
        const ctx = canvas.getContext('2d');
        function resize() { canvas.width = window.innerWidth; canvas.height = window.innerHeight; }
        window.onresize = resize; resize();
        function drawBg() { ctx.fillStyle = '#020617'; ctx.fillRect(0,0,canvas.width,canvas.height); requestAnimationFrame(drawBg); }
        drawBg();

        // --- Dual Terminal Logic ---
        socket.on('terminal_output', data => {
            const libTerm = document.getElementById('lib-terminal');
            const outTerm = document.getElementById('out-terminal');
            
            // যদি আউটপুটে pip বা installation সংক্রান্ত কিছু থাকে, তবে লাইব্রেরি টার্মিনালে যাবে
            if(data.output.toLowerCase().includes('pip') || 
               data.output.toLowerCase().includes('install') || 
               data.output.toLowerCase().includes('requirement')) {
                libTerm.innerHTML += `<div style="margin-bottom:2px;">${data.output}</div>`;
                libTerm.scrollTop = libTerm.scrollHeight;
            } else {
                // বাকি সব আউটপুট এক্সিকিউশন টার্মিনালে যাবে
                outTerm.innerHTML += `<div style="margin-bottom:2px;">> ${data.output}</div>`;
                outTerm.scrollTop = outTerm.scrollHeight;
            }
        });

        function sendCmd() {
            const cmdInput = document.getElementById('cmd');
            if(!cmdInput.value) return;
            document.getElementById('lib-terminal').innerHTML += `<div style="color:var(--purple);">$ ${cmdInput.value}</div>`;
            socket.emit('terminal_command', {command: cmdInput.value});
            cmdInput.value = '';
        }

        function runCode(btn) {
            const filename = document.getElementById('filename').value;
            const content = document.getElementById('code').value;
            const outTerm = document.getElementById('out-terminal');
            
            outTerm.innerHTML = `<div style="color:var(--cyan);">[SYSTEM] Running ${filename}...</div>`;
            socket.emit('save_file', {filename, content});
            socket.emit('run_code', {filename});
            
            btn.innerHTML = '<i data-lucide="loader" class="spin"></i> Running...';
            lucide.createIcons();
            setTimeout(() => { 
                btn.innerHTML = '<i data-lucide="play"></i> Run Code'; 
                lucide.createIcons(); 
            }, 1500);
        }
        
        // Autosave code on change
        let saveTimer;
        document.getElementById('code').addEventListener('input', function() {
            clearTimeout(saveTimer);
            saveTimer = setTimeout(() => {
                const filename = document.getElementById('filename').value;
                const content = document.getElementById('code').value;
                socket.emit('save_file', {filename, content});
            }, 1000);
        });
    </script>
</body>
</html>
'''

# ডাটাবেজ ইনিশিয়ালাইজেশন
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE,
                  ip_address TEXT,
                  project_name TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Code files table
    c.execute('''CREATE TABLE IF NOT EXISTS code_files
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  filename TEXT,
                  content TEXT,
                  project_name TEXT,
                  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users(id),
                  UNIQUE(user_id, filename, project_name))''')
    
    # Libraries table
    c.execute('''CREATE TABLE IF NOT EXISTS libraries
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  package_name TEXT,
                  version TEXT,
                  command TEXT,
                  project_name TEXT,
                  installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    # Terminal logs table
    c.execute('''CREATE TABLE IF NOT EXISTS terminal_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  terminal_type TEXT,
                  command TEXT,
                  output TEXT,
                  project_name TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    
    conn.commit()
    conn.close()

init_db()

def get_db():
    return sqlite3.connect(DB_PATH)

def get_or_create_user(username, ip_address, project_name):
    conn = get_db()
    c = conn.cursor()
    
    # Check if user exists
    c.execute('SELECT id FROM users WHERE username = ? AND project_name = ?', 
              (username, project_name))
    user = c.fetchone()
    
    if user:
        user_id = user[0]
    else:
        # Create new user
        c.execute('INSERT INTO users (username, ip_address, project_name) VALUES (?, ?, ?)',
                  (username, ip_address, project_name))
        user_id = c.lastrowid
    
    conn.commit()
    conn.close()
    return user_id

def save_code_to_db(user_id, filename, content, project_name):
    conn = get_db()
    c = conn.cursor()
    
    # Save to database
    c.execute('''INSERT OR REPLACE INTO code_files 
                 (user_id, filename, content, project_name) 
                 VALUES (?, ?, ?, ?)''',
              (user_id, filename, content, project_name))
    
    # Also save to file system
    user_dir = CODE_DIR / str(user_id)
    user_dir.mkdir(exist_ok=True)
    
    file_path = user_dir / filename
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    conn.commit()
    conn.close()

def save_library_to_db(user_id, package_name, version, command, project_name):
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO libraries 
                 (user_id, package_name, version, command, project_name) 
                 VALUES (?, ?, ?, ?, ?)''',
              (user_id, package_name, version, command, project_name))
    conn.commit()
    conn.close()

def save_terminal_log(user_id, terminal_type, command, output, project_name):
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO terminal_logs 
                 (user_id, terminal_type, command, output, project_name) 
                 VALUES (?, ?, ?, ?, ?)''',
              (user_id, terminal_type, command, output, project_name))
    conn.commit()
    conn.close()

def get_user_data(user_id, project_name):
    conn = get_db()
    c = conn.cursor()
    
    # Get default code file
    c.execute('''SELECT filename, content FROM code_files 
                 WHERE user_id = ? AND project_name = ? 
                 ORDER BY updated_at DESC LIMIT 1''',
              (user_id, project_name))
    file_data = c.fetchone()
    
    # Get installed libraries
    c.execute('''SELECT package_name, version FROM libraries 
                 WHERE user_id = ? AND project_name = ? 
                 ORDER BY installed_at DESC''',
              (user_id, project_name))
    libraries = c.fetchall()
    
    conn.close()
    
    return {
        'default_file': file_data[0] if file_data else 'main.py',
        'default_content': file_data[1] if file_data else '# Write code here...',
        'libraries': libraries
    }

# রাউটস
@app.route('/', methods=['GET', 'POST'])
def index():
    if 'user_id' in session and 'project_name' in session:
        user_data = get_user_data(session['user_id'], session['project_name'])
        return render_template_string(HTML_TEMPLATE, 
                                    user_id=session['user_id'],
                                    default_file=user_data['default_file'],
                                    default_content=user_data['default_content'])
    
    return render_template_string(HTML_TEMPLATE, user_id=None)

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username', '').strip()
    project_name = request.form.get('project_name', 'default').strip()
    
    if not username:
        return redirect('/')
    
    user_id = get_or_create_user(username, request.remote_addr, project_name)
    
    session['user_id'] = user_id
    session['username'] = username
    session['project_name'] = project_name
    
    return redirect('/')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/api/user_data')
def api_user_data():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'})
    
    user_data = get_user_data(session['user_id'], session.get('project_name', 'default'))
    return jsonify(user_data)

@app.route('/api/projects')
def api_projects():
    if 'username' not in session:
        return jsonify({'error': 'Not logged in'})
    
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT DISTINCT project_name FROM users 
                 WHERE username = ? ORDER BY created_at DESC''',
              (session['username'],))
    projects = [row[0] for row in c.fetchall()]
    conn.close()
    
    return jsonify({'projects': projects})

# WebSocket হ্যান্ডলারস
@socketio.on('connect')
def handle_connect():
    if 'user_id' in session:
        emit('terminal_output', {'output': f'[SYSTEM] Connected as {session["username"]} ({session["project_name"]})'})

@socketio.on('save_file')
def handle_save_file(data):
    if 'user_id' not in session:
        return
    
    filename = data.get('filename', 'main.py')
    content = data.get('content', '')
    project_name = session.get('project_name', 'default')
    
    save_code_to_db(session['user_id'], filename, content, project_name)
    emit('terminal_output', {'output': f'[SYSTEM] Saved {filename}'})

@socketio.on('run_code')
def handle_run_code(data):
    if 'user_id' not in session:
        return
    
    filename = data.get('filename', 'main.py')
    project_name = session.get('project_name', 'default')
    user_dir = CODE_DIR / str(session['user_id'])
    file_path = user_dir / filename
    
    if not file_path.exists():
        emit('terminal_output', {'output': f'[ERROR] File {filename} not found'})
        return
    
    def run_python_code():
        try:
            # Run the code
            process = subprocess.Popen(
                ['python', str(file_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(user_dir)
            )
            
            # Read output in real-time
            for line in process.stdout:
                if line.strip():
                    emit('terminal_output', {'output': line.strip()})
                    save_terminal_log(
                        session['user_id'], 
                        'exec', 
                        f'python {filename}', 
                        line.strip(),
                        project_name
                    )
            
            process.wait()
            
        except Exception as e:
            error_msg = f'[ERROR] {str(e)}'
            emit('terminal_output', {'output': error_msg})
            save_terminal_log(
                session['user_id'], 
                'exec', 
                f'python {filename}', 
                error_msg,
                project_name
            )
    
    # Run in background thread
    thread = threading.Thread(target=run_python_code)
    thread.start()

@socketio.on('terminal_command')
def handle_terminal_command(data):
    if 'user_id' not in session:
        return
    
    command = data.get('command', '').strip()
    project_name = session.get('project_name', 'default')
    
    if not command:
        return
    
    emit('terminal_output', {'output': f'$ {command}'})
    
    def execute_command():
        try:
            # Check if it's a pip install command
            is_pip_install = command.startswith('pip install')
            
            # Run command
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(CODE_DIR / str(session['user_id']))
            )
            
            # Read output
            output_lines = []
            for line in process.stdout:
                if line.strip():
                    output = line.strip()
                    emit('terminal_output', {'output': output})
                    output_lines.append(output)
            
            process.wait()
            full_output = '\n'.join(output_lines)
            
            # Save terminal log
            terminal_type = 'lib' if is_pip_install else 'cmd'
            save_terminal_log(
                session['user_id'],
                terminal_type,
                command,
                full_output,
                project_name
            )
            
            # If pip install, save library info
            if is_pip_install:
                # Parse package name from command
                parts = command.split()
                if len(parts) >= 3:
                    package_name = parts[2]
                    # Try to extract version
                    version = 'latest'
                    if '==' in package_name:
                        package_name, version = package_name.split('==')
                    
                    save_library_to_db(
                        session['user_id'],
                        package_name,
                        version,
                        command,
                        project_name
                    )
                    
        except Exception as e:
            error_msg = f'[ERROR] Command failed: {str(e)}'
            emit('terminal_output', {'output': error_msg})
            save_terminal_log(
                session['user_id'],
                'error',
                command,
                error_msg,
                project_name
            )
    
    # Run in background thread
    thread = threading.Thread(target=execute_command)
    thread.start()

@app.route('/api/export/<username>/<project_name>')
def export_project(username, project_name):
    """Export project data as JSON"""
    conn = get_db()
    c = conn.cursor()
    
    # Get user ID
    c.execute('SELECT id FROM users WHERE username = ? AND project_name = ?',
              (username, project_name))
    user = c.fetchone()
    
    if not user:
        return jsonify({'error': 'Project not found'})
    
    user_id = user[0]
    
    # Get all data
    c.execute('SELECT filename, content FROM code_files WHERE user_id = ? AND project_name = ?',
              (user_id, project_name))
    code_files = [{'filename': row[0], 'content': row[1]} for row in c.fetchall()]
    
    c.execute('SELECT package_name, version, command FROM libraries WHERE user_id = ? AND project_name = ?',
              (user_id, project_name))
    libraries = [{'package': row[0], 'version': row[1], 'command': row[2]} for row in c.fetchall()]
    
    conn.close()
    
    return jsonify({
        'username': username,
        'project_name': project_name,
        'code_files': code_files,
        'libraries': libraries,
        'exported_at': datetime.now().isoformat()
    })

# Cleanup old files periodically
def cleanup_old_files():
    """Clean up files older than 30 days"""
    while True:
        try:
            for user_dir in CODE_DIR.iterdir():
                if user_dir.is_dir():
                    for file in user_dir.iterdir():
                        # Check if file is older than 30 days
                        if file.stat().st_mtime < time.time() - (30 * 24 * 3600):
                            file.unlink()
        except:
            pass
        
        time.sleep(24 * 3600)  # Run once per day

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()

if __name__ == '__main__':
    print("=" * 50)
    print("Cyber 20 UN IDE Server Starting...")
    print("=" * 50)
    print(f"Database: {DB_PATH}")
    print(f"Code directory: {CODE_DIR}")
    print(f"Access URL: http://localhost:5000")
    print(f"Local network URL: http://{os.popen('hostname -I').read().strip()}:5000")
    print("=" * 50)
    
    # Create virtual environment if not exists
    if not os.path.exists('venv'):
        print("Creating virtual environment...")
        subprocess.run(['python', '-m', 'venv', 'venv'], check=False)
        print("Virtual environment created at 'venv/'")
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
