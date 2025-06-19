import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Заміни на свій секретний ключ
UPLOAD_FOLDER = 'static/uploads/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            author TEXT NOT NULL,
            tags TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS menu (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT NOT NULL
        );
    ''')
    # Створити меню, якщо ще не існує
    existing_menu = conn.execute("SELECT COUNT(*) FROM menu").fetchone()[0]
    if existing_menu == 0:
        conn.executemany("INSERT INTO menu (title, url) VALUES (?, ?)", [
            ('Головна', '/'),
            ('Про додаток', '/about'),
            ('Слайдшоу', '/slideshow')
        ])
    # Додати адміна, якщо ще нема
    cursor = conn.execute("SELECT * FROM users WHERE username = 'admin'")
    if cursor.fetchone() is None:
        conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", ('admin', 'admin123'))
    conn.commit()
    conn.close()

@app.context_processor
def inject_menu():
    conn = get_db_connection()
    menu = conn.execute('SELECT * FROM menu').fetchall()
    conn.close()
    return dict(menu=menu)

@app.route('/')
def index():
    conn = get_db_connection()
    photos = conn.execute('SELECT * FROM photos ORDER BY timestamp DESC').fetchall()
    conn.close()
    return render_template('index.html', photos=photos)

@app.route('/tag/<tag>')
def tag(tag):
    conn = get_db_connection()
    photos = conn.execute("SELECT * FROM photos WHERE tags LIKE ? ORDER BY timestamp DESC", (f'%{tag}%',)).fetchall()
    conn.close()
    return render_template('index.html', photos=photos, filter_tag=tag)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('admin'))
        else:
            error = 'Неправильний логін або пароль'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/admin')
def admin():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    photos = conn.execute('SELECT * FROM photos ORDER BY timestamp DESC').fetchall()
    conn.close()
    return render_template('admin.html', photos=photos)

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        file = request.files.get('photo')
        author = request.form.get('author', '').strip()
        tags = request.form.get('tags', '').strip()
        if not file or file.filename == '':
            flash('Будь ласка, виберіть файл для завантаження.')
            return redirect(request.url)
        if not author:
            flash('Будь ласка, введіть автора.')
            return redirect(request.url)
        if not tags:
            flash('Будь ласка, введіть теги.')
            return redirect(request.url)
        filename = file.filename
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        counter = 1
        original_filename, file_extension = os.path.splitext(filename)
        while os.path.exists(filepath):
            filename = f"{original_filename}_{counter}{file_extension}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            counter += 1
        file.save(filepath)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO photos (filename, author, tags, timestamp) VALUES (?, ?, ?, ?)',
            (filename, author, tags, timestamp)
        )
        conn.commit()
        conn.close()
        flash('Фото успішно завантажено!')
        return redirect(url_for('admin'))
    return render_template('upload.html')

@app.route('/delete/<int:photo_id>', methods=['POST'])
def delete_photo(photo_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    photo = conn.execute('SELECT filename FROM photos WHERE id = ?', (photo_id,)).fetchone()
    if photo:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], photo['filename'])
        if os.path.exists(filepath):
            os.remove(filepath)
        conn.execute('DELETE FROM photos WHERE id = ?', (photo_id,))
        conn.commit()
    conn.close()
    flash('Фото видалено.')
    return redirect(url_for('admin'))

@app.route('/edit/<int:photo_id>', methods=['GET', 'POST'])
def edit_photo(photo_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    photo = conn.execute('SELECT * FROM photos WHERE id = ?', (photo_id,)).fetchone()
    if photo is None:
        conn.close()
        flash('Фото не знайдено.')
        return redirect(url_for('admin'))
    if request.method == 'POST':
        author = request.form.get('author', '').strip()
        tags = request.form.get('tags', '').strip()
        if not author or not tags:
            flash('Автор та теги не можуть бути порожніми.')
            return redirect(request.url)
        conn.execute(
            'UPDATE photos SET author = ?, tags = ? WHERE id = ?',
            (author, tags, photo_id)
        )
        conn.commit()
        conn.close()
        flash('Фото оновлено.')
        return redirect(url_for('admin'))
    conn.close()
    return render_template('edit.html', photo=photo)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/slideshow')
def slideshow():
    conn = get_db_connection()
    photos = conn.execute('SELECT * FROM photos ORDER BY timestamp DESC').fetchall()
    conn.close()
    photos = [dict(row) for row in photos]
    return render_template('slideshow.html', photos=photos)

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5001)
