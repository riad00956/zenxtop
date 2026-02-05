from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import SocketIO, emit
import subprocess
import os
import sqlite3
from datetime import datetime
import json
from threading import Lock
import time
import atexit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'cyber20un_secret_key_2024'
socketio = SocketIO(app, cors_allowed_origins="*")

# Database setup
DB_NAME = 'cyber20un.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        ip_address TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS code_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT,
        content TEXT,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS installed_libraries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        library_name TEXT,
        version TEXT,
        command TEXT,
        user_id INTEGER,
        installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS terminal_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        terminal_type TEXT,
        command TEXT,
        output TEXT,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    
    conn.commit()
    conn.close()

init_db()

def get_user_id():
    """Get or create user based on session/IP"""
    if 'user_id' in session:
        return session['user_id']
    
    # Create new user based on IP
    ip_address = request.remote_addr
    username = f"user_{int(time.time())}_{ip_address.replace('.', '_')}"
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('INSERT OR IGNORE INTO users (username, ip_address) VALUES (?, ?)', 
                   (username, ip_address))
    
    cursor.execute('SELECT id FROM users WHERE ip_address = ?', (ip_address,))
    user = cursor.fetchone()
    
    if user:
        session['user_id'] = user[0]
        session['username'] = username
        conn.close()
        return user[0]
    
    conn.close()
    return None

def save_code_file(filename, content, user_id):
    """Save code to database"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Check if file exists for this user
    cursor.execute('SELECT id FROM code_files WHERE filename = ? AND user_id = ?', 
                   (filename, user_id))
    existing = cursor.fetchone()
    
    if existing:
        cursor.execute('UPDATE code_files SET content = ?, created_at = CURRENT_TIMESTAMP WHERE id = ?', 
                       (content, existing[0]))
    else:
        cursor.execute('INSERT INTO code_files (filename, content, user_id) VALUES (?, ?, ?)', 
                       (filename, content, user_id))
    
    conn.commit()
    conn.close()

def save_library_install(command, output, user_id):
    """Save library installation to database"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Extract library names from command
    libs = []
    if 'install' in command.lower():
        parts = command.lower().split('install')
        if len(parts) > 1:
            libs = [lib.strip() for lib in parts[1].split() if lib.strip()]
    
    for lib in libs:
        # Remove version specifiers
        lib_name = lib.split('==')[0].split('>')[0].split('<')[0].split('~=')[0]
        
        # Extract version from output if available
        version = "unknown"
        lines = output.split('\n')
        for line in lines:
            if lib_name.lower() in line.lower() and 'already satisfied' in line.lower():
                if '==' in line:
                    version = line.split('==')[-1].strip()
                break
        
        cursor.execute('''
        INSERT INTO installed_libraries (library_name, version, command, user_id) 
        VALUES (?, ?, ?, ?)
        ''', (lib_name, version, command, user_id))
    
    conn.commit()
    conn.close()

def save_terminal_log(terminal_type, command, output, user_id):
    """Save terminal activity to database"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO terminal_logs (terminal_type, command, output, user_id) 
    VALUES (?, ?, ?, ?)
    ''', (terminal_type, command[:500], output[:10000], user_id))
    
    conn.commit()
    conn.close()

def load_user_data(user_id):
    """Load user's saved data"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Get code files
    cursor.execute('SELECT filename, content FROM code_files WHERE user_id = ? ORDER BY created_at DESC', 
                   (user_id,))
    code_files = cursor.fetchall()
    
    # Get installed libraries
    cursor.execute('''
    SELECT DISTINCT library_name, version 
    FROM installed_libraries 
    WHERE user_id = ? 
    ORDER BY installed_at DESC
    ''', (user_id,))
    libraries = cursor.fetchall()
    
    # Get recent terminal logs
    cursor.execute('''
    SELECT terminal_type, command, output 
    FROM terminal_logs 
    WHERE user_id = ? 
    ORDER BY created_at DESC 
    LIMIT 50
    ''', (user_id,))
    logs = cursor.fetchall()
    
    conn.close()
    
    return {
        'code_files': code_files,
        'libraries': libraries,
        'logs': logs
    }

@app.route('/')
def index():
    user_id = get_user_id()
    if user_id:
        user_data = load_user_data(user_id)
        
        # Find main.py or first file
        default_file = 'main.py'
        default_content = '# Write code here...'
        
        for filename, content in user_data['code_files']:
            if filename == 'main.py':
                default_file = filename
                default_content = content
                break
        elif user_data['code_files']:
            default_file = user_data['code_files'][0][0]
            default_content = user_data['code_files'][0][1]
        
        return render_template('index.html', 
                             default_file=default_file,
                             default_content=default_content,
                             libraries=user_data['libraries'],
                             logs=user_data['logs'])
    return render_template('index.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# Create code_files directory if not exists
if not os.path.exists('code_files'):
    os.makedirs('code_files')

def run_command_in_virtualenv(command, user_id, terminal_type="lib"):
    """Run command in virtual environment"""
    try:
        # Activate virtualenv if exists
        if os.path.exists('venv'):
            if os.name == 'nt':  # Windows
                activate_cmd = 'venv\\Scripts\\activate && '
            else:  # Unix/Linux/Mac
                activate_cmd = 'source venv/bin/activate && '
            full_command = f'{activate_cmd}{command}'
        else:
            full_command = command
        
        # Run the command
        process = subprocess.Popen(
            full_command if os.name == 'nt' else ['bash', '-c', full_command],
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd='.'  # Run in current directory
        )
        
        output_lines = []
        # Read output in real-time
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                output_lines.append(output.strip())
                # Send to WebSocket
                socketio.emit('terminal_output', {'output': output.strip()})
        
        # Get any remaining output
        stdout, stderr = process.communicate()
        if stderr:
            output_lines.append(f"ERROR: {stderr.strip()}")
            socketio.emit('terminal_output', {'output': f"ERROR: {stderr.strip()}"})
        
        full_output = '\n'.join(output_lines)
        
        # Save to database
        save_terminal_log(terminal_type, command, full_output, user_id)
        
        # If pip install, save libraries
        if 'pip' in command and 'install' in command:
            save_library_install(command, full_output, user_id)
        
        return full_output
        
    except Exception as e:
        error_msg = f"Command execution error: {str(e)}"
        socketio.emit('terminal_output', {'output': error_msg})
        save_terminal_log(terminal_type, command, error_msg, user_id)
        return error_msg

@socketio.on('connect')
def handle_connect():
    user_id = get_user_id()
    print(f"Client connected - User ID: {user_id}")
    
    # Send initial terminal state
    if user_id:
        user_data = load_user_data(user_id)
        
        # Send recent library logs
        lib_logs = [log for log in user_data['logs'] if log[0] == 'lib']
        for log in lib_logs[:10]:  # Last 10 library logs
            emit('terminal_output', {'output': log[2]})
        
        # Send message
        emit('terminal_output', {'output': f"[SYSTEM] Connected as {session.get('username', 'Guest')}"})

@socketio.on('terminal_command')
def handle_terminal_command(data):
    user_id = get_user_id()
    if not user_id:
        return
    
    command = data.get('command', '').strip()
    if not command:
        return
    
    # Run the command
    run_command_in_virtualenv(command, user_id, "lib")

@socketio.on('save_file')
def handle_save_file(data):
    user_id = get_user_id()
    if not user_id:
        return
    
    filename = data.get('filename', 'main.py').strip()
    content = data.get('content', '')
    
    # Save to database
    save_code_file(filename, content, user_id)
    
    # Also save to file system for execution
    filepath = os.path.join('code_files', f"{user_id}_{filename}")
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"File saved: {filename} for user {user_id}")

@socketio.on('run_code')
def handle_run_code(data):
    user_id = get_user_id()
    if not user_id:
        return
    
    filename = data.get('filename', 'main.py').strip()
    filepath = os.path.join('code_files', f"{user_id}_{filename}")
    
    if not os.path.exists(filepath):
        socketio.emit('terminal_output', {'output': f"[ERROR] File {filename} not found!"})
        return
    
    # Run the Python code
    try:
        if os.path.exists('venv'):
            if os.name == 'nt':  # Windows
                python_cmd = 'venv\\Scripts\\python'
            else:  # Unix/Linux/Mac
                python_cmd = 'venv/bin/python'
        else:
            python_cmd = 'python'
        
        command = f'{python_cmd} "{filepath}"'
        
        # Run the code
        socketio.emit('terminal_output', {'output': f"[SYSTEM] Executing {filename}..."})
        
        process = subprocess.Popen(
            command if os.name == 'nt' else ['bash', '-c', command],
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Read output in real-time
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                socketio.emit('terminal_output', {'output': output.strip()})
        
        # Get any remaining output
        stdout, stderr = process.communicate()
        if stdout:
            socketio.emit('terminal_output', {'output': stdout.strip()})
        if stderr:
            socketio.emit('terminal_output', {'output': f"ERROR: {stderr.strip()}"})
        
        # Save execution log
        full_output = (stdout + stderr) if stderr else stdout
        save_terminal_log("exec", f"python {filename}", full_output, user_id)
        
    except Exception as e:
        error_msg = f"[ERROR] Execution failed: {str(e)}"
        socketio.emit('terminal_output', {'output': error_msg})
        save_terminal_log("exec", f"python {filename}", error_msg, user_id)

# Admin route to view all data (optional)
@app.route('/admin')
def admin():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM users')
    user_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM code_files')
    file_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(DISTINCT library_name) FROM installed_libraries')
    lib_count = cursor.fetchone()[0]
    
    conn.close()
    
    return f"""
    <h1>Cyber 20 UN Admin</h1>
    <p>Total Users: {user_count}</p>
    <p>Code Files: {file_count}</p>
    <p>Unique Libraries: {lib_count}</p>
    <p><a href="/">Back to IDE</a></p>
    """

# Cleanup function
def cleanup_old_files():
    """Clean up old temporary files"""
    try:
        for file in os.listdir('code_files'):
            if file.endswith('.py'):
                filepath = os.path.join('code_files', file)
                # Remove files older than 7 days
                if os.path.getmtime(filepath) < time.time() - (7 * 24 * 3600):
                    os.remove(filepath)
    except:
        pass

atexit.register(cleanup_old_files)

if __name__ == '__main__':
    print("Cyber 20 UN IDE Server Starting...")
    print("Database initialized at:", DB_NAME)
    print("Access the IDE at: http://localhost:5000")
    print("Access admin panel at: http://localhost:5000/admin")
    
    # Create virtual environment if not exists
    if not os.path.exists('venv'):
        print("Note: Virtual environment not found. Creating one...")
        os.system('python -m venv venv')
        print("Virtual environment created. Install packages with: pip install <package>")
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
