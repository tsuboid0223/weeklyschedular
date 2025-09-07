import streamlit as st
import pandas as pd
import json
import base64
from datetime import datetime, timedelta
from PIL import Image
import io
import uuid

# ページ設定
st.set_page_config(
    page_title="週間タスクスケジューラー",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# カスタムCSS
st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #1f2937;
        margin-bottom: 2rem;
    }
    .week-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 1rem;
    }
    .day-column {
        background: #f8fafc;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem;
        min-height: 400px;
        border: 2px solid #e2e8f0;
    }
    .task-card {
        background: white;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #3b82f6;
    }
    .task-card.high {
        border-left-color: #ef4444;
    }
    .task-card.medium {
        border-left-color: #f59e0b;
    }
    .task-card.low {
        border-left-color: #10b981;
    }
    .priority-badge {
        display: inline-block;
        padding: 0.25rem 0.5rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: bold;
        margin-right: 0.5rem;
    }
    .priority-high {
        background-color: #fecaca;
        color: #dc2626;
    }
    .priority-medium {
        background-color: #fed7aa;
        color: #ea580c;
    }
    .priority-low {
        background-color: #bbf7d0;
        color: #059669;
    }
    .label-tag {
        display: inline-block;
        background: #e0e7ff;
        color: #3730a3;
        padding: 0.2rem 0.5rem;
        border-radius: 12px;
        font-size: 0.75rem;
        margin: 0.1rem;
    }
</style>
""", unsafe_allow_html=True)

# データクラス
class Task:
    def __init__(self, id=None, title="", description="", date="", priority="medium", labels=None, attachments=None):
        self.id = id or str(uuid.uuid4())
        self.title = title
        self.description = description
        self.date = date
        self.priority = priority
        self.labels = labels or []
        self.attachments = attachments or []
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'date': self.date,
            'priority': self.priority,
            'labels': self.labels,
            'attachments': self.attachments,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data):
        task = cls(
            id=data['id'],
            title=data['title'],
            description=data['description'],
            date=data['date'],
            priority=data['priority'],
            labels=data['labels'],
            attachments=data['attachments']
        )
        if 'created_at' in data:
            task.created_at = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data:
            task.updated_at = datetime.fromisoformat(data['updated_at'])
        return task

# セッション状態の初期化
if 'tasks' not in st.session_state:
    st.session_state.tasks = []
if 'current_week' not in st.session_state:
    st.session_state.current_week = datetime.now().date()

# ユーティリティ関数
def get_week_dates(start_date):
    """指定した日付を含む週の日付リストを取得"""
    # 月曜日を週の開始とする
    days_since_monday = start_date.weekday()
    monday = start_date - timedelta(days=days_since_monday)
    return [monday + timedelta(days=i) for i in range(7)]

def format_date_jp(date):
    """日本語形式で日付をフォーマット"""
    weekdays = ['月', '火', '水', '木', '金', '土', '日']
    return f"{date.month}/{date.day}({weekdays[date.weekday()]})"

def get_tasks_for_date(date_str):
    """指定した日付のタスクを取得"""
    return [task for task in st.session_state.tasks if task.date == date_str]

def save_task(task):
    """タスクを保存"""
    # 既存のタスクを更新または新規追加
    existing_index = None
    for i, existing_task in enumerate(st.session_state.tasks):
        if existing_task.id == task.id:
            existing_index = i
            break
    
    if existing_index is not None:
        st.session_state.tasks[existing_index] = task
    else:
        st.session_state.tasks.append(task)
    
    # データをJSON形式でエクスポート可能にする
    if 'tasks_json' not in st.session_state:
        st.session_state.tasks_json = ""
    
    tasks_data = [task.to_dict() for task in st.session_state.tasks]
    st.session_state.tasks_json = json.dumps(tasks_data, ensure_ascii=False, indent=2)

def delete_task(task_id):
    """タスクを削除"""
    st.session_state.tasks = [task for task in st.session_state.tasks if task.id != task_id]
    tasks_data = [task.to_dict() for task in st.session_state.tasks]
    st.session_state.tasks_json = json.dumps(tasks_data, ensure_ascii=False, indent=2)

def process_uploaded_image(uploaded_file):
    """アップロードされた画像を処理"""
    if uploaded_file is not None:
        # 画像をbase64エンコード
        image_data = uploaded_file.read()
        base64_data = base64.b64encode(image_data).decode()
        
        return {
            'id': str(uuid.uuid4()),
            'name': uploaded_file.name,
            'type': uploaded_file.type,
            'size': len(image_data),
            'data': f"data:{uploaded_file.type};base64,{base64_data}"
        }
    return None

# メインアプリケーション
def main():
    # ヘッダー
    st.markdown('<h1 class="main-header">📅 週間タスクスケジューラー</h1>', unsafe_allow_html=True)
    
    # サイドバー
    with st.sidebar:
        st.header("⚙️ 設定")
        
        # 週選択
        week_start = st.date_input(
            "週を選択",
            value=st.session_state.current_week,
            key="week_selector"
        )
        st.session_state.current_week = week_start
        
        # タスク統計
        st.subheader("📊 タスク統計")
        total_tasks = len(st.session_state.tasks)
        high_priority = len([t for t in st.session_state.tasks if t.priority == 'high'])
        st.metric("総タスク数", total_tasks)
        st.metric("高優先度", high_priority)
        
        # データ管理
        st.subheader("💾 データ管理")
        
        # JSONエクスポート
        if st.session_state.tasks:
            tasks_data = [task.to_dict() for task in st.session_state.tasks]
            json_data = json.dumps(tasks_data, ensure_ascii=False, indent=2)
            st.download_button(
                label="📥 JSONダウンロード",
                data=json_data,
                file_name=f"tasks_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json"
            )
        
        # データクリア
        if st.button("🗑️ 全データクリア", type="secondary"):
            if st.checkbox("本当に削除しますか？"):
                st.session_state.tasks = []
                st.rerun()
    
    # 週表示
    week_dates = get_week_dates(st.session_state.current_week)
    week_start_str = week_dates[0].strftime("%Y/%m/%d")
    week_end_str = week_dates[6].strftime("%Y/%m/%d")
    
    st.markdown(f'<div class="week-header"><h2>📅 {week_start_str} - {week_end_str}</h2></div>', unsafe_allow_html=True)
    
    # 新しいタスク作成
    with st.expander("➕ 新しいタスクを作成", expanded=False):
        with st.form("new_task_form"):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                title = st.text_input("タスクタイトル *", placeholder="例: 会議準備")
                description = st.text_area("説明", placeholder="詳細な説明を入力...")
            
            with col2:
                task_date = st.date_input("日付", value=datetime.now().date())
                priority = st.selectbox("優先度", ["low", "medium", "high"], index=1)
                labels_input = st.text_input("ラベル (カンマ区切り)", placeholder="会議,重要")
            
            # 画像アップロード
            uploaded_file = st.file_uploader("画像を添付", type=['png', 'jpg', 'jpeg', 'gif'])
            
            submitted = st.form_submit_button("💾 タスクを保存")
            
            if submitted and title:
                # ラベル処理
                labels = [label.strip() for label in labels_input.split(',') if label.strip()]
                
                # 添付ファイル処理
                attachments = []
                if uploaded_file:
                    attachment = process_uploaded_image(uploaded_file)
                    if attachment:
                        attachments.append(attachment)
                
                # タスク作成
                new_task = Task(
                    title=title,
                    description=description,
                    date=task_date.strftime("%Y-%m-%d"),
                    priority=priority,
                    labels=labels,
                    attachments=attachments
                )
                
                save_task(new_task)
                st.success(f"✅ タスク「{title}」を作成しました！")
                st.rerun()
    
    # 週間ビュー
    cols = st.columns(7)
    weekdays = ['月曜日', '火曜日', '水曜日', '木曜日', '金曜日', '土曜日', '日曜日']
    
    for i, (date, col, weekday) in enumerate(zip(week_dates, cols, weekdays)):
        with col:
            date_str = date.strftime("%Y-%m-%d")
            date_display = format_date_jp(date)
            
            st.markdown(f"### {weekday}")
            st.markdown(f"**{date_display}**")
            
            # その日のタスクを取得
            day_tasks = get_tasks_for_date(date_str)
            
            if not day_tasks:
                st.markdown('<div class="day-column">タスクなし</div>', unsafe_allow_html=True)
            else:
                for task in day_tasks:
                    # 優先度に応じたスタイル
                    priority_class = f"task-card {task.priority}"
                    priority_badge_class = f"priority-badge priority-{task.priority}"
                    
                    # タスクカード
                    with st.container():
                        st.markdown(f'<div class="{priority_class}">', unsafe_allow_html=True)
                        
                        # タイトルと優先度
                        col_title, col_actions = st.columns([3, 1])
                        with col_title:
                            st.markdown(f"**{task.title}**")
                            if task.priority != 'medium':
                                priority_text = {'high': '高', 'medium': '中', 'low': '低'}[task.priority]
                                st.markdown(f'<span class="{priority_badge_class}">{priority_text}</span>', unsafe_allow_html=True)
                        
                        with col_actions:
                            if st.button("🗑️", key=f"delete_{task.id}", help="削除"):
                                delete_task(task.id)
                                st.rerun()
                        
                        # 説明
                        if task.description:
                            st.markdown(f"<small>{task.description}</small>", unsafe_allow_html=True)
                        
                        # ラベル
                        if task.labels:
                            labels_html = ''.join([f'<span class="label-tag">{label}</span>' for label in task.labels])
                            st.markdown(labels_html, unsafe_allow_html=True)
                        
                        # 添付画像
                        if task.attachments:
                            st.markdown("**📎 添付ファイル:**")
                            for attachment in task.attachments:
                                if attachment['type'].startswith('image/'):
                                    # base64データから画像を復元
                                    try:
                                        image_data = attachment['data'].split(',')[1]
                                        image_bytes = base64.b64decode(image_data)
                                        image = Image.open(io.BytesIO(image_bytes))
                                        st.image(image, caption=attachment['name'], width=150)
                                    except Exception as e:
                                        st.error(f"画像の表示エラー: {str(e)}")
                        
                        st.markdown('</div>', unsafe_allow_html=True)
                        st.markdown("---")

if __name__ == "__main__":
    main()