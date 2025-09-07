import streamlit as st
import json
import base64
from datetime import datetime, timedelta
from PIL import Image
import io
import uuid
import inspect
import re
import hashlib
from pathlib import Path
import threading
from contextlib import contextmanager


オプション依存（未インストールでもアプリは動く）

ドラッグ＆ドロップ: streamlit-sortables

try:
from streamlit_sortables import sort_items
SORTABLE_AVAILABLE = True
except Exception:
SORTABLE_AVAILABLE = False


サムネイル画像のクリック対応: streamlit-extras

try:
from streamlit_extras.clickable_images import clickable_images
CLICKABLE_AVAILABLE = True
except Exception:
CLICKABLE_AVAILABLE = False


ページ設定

st.set_page_config(
page_title="週間タスクスケジューラー",
page_icon="📅",
layout="wide",
initial_sidebar_state="expanded"
)


カスタムCSS（見やすさ・レイアウト安定）

st.markdown("""



""", unsafe_allow_html=True)


永続化（同一デプロイ中のリロードでも保持）

DATA_FILE = Path("tasks_store.json")
_PERSIST_LOCK = threading.Lock()


def load_tasks_from_disk():
if DATA_FILE.exists():
try:
return json.loads(DATA_FILE.read_text(encoding="utf-8"))
except Exception:
return []
return []


def persist_tasks_to_disk(task_dicts):
try:
with _PERSIST_LOCK:
DATA_FILE.write_text(json.dumps(task_dicts, ensure_ascii=False, indent=2), encoding="utf-8")
except Exception:
pass


データクラス

class Task:
def init(self, id=None, title="", description="", date="", priority="medium", labels=None, attachments=None):
self.id = id or str(uuid.uuid4())
self.title = title
self.description = description
self.date = date  # "YYYY-MM-DD"
self.priority = priority  # low/medium/high
self.labels = labels or []
self.attachments = attachments or []  # base64データURIの添付
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
        labels=data.get('labels', []),
        attachments=data.get('attachments', [])
    )
    try:
        if data.get('created_at'):
            task.created_at = datetime.fromisoformat(data['created_at'])
    except Exception:
        task.created_at = datetime.now()
    try:
        if data.get('updated_at'):
            task.updated_at = datetime.fromisoformat(data['updated_at'])
    except Exception:
        task.updated_at = datetime.now()
    return task

セッション状態（初回のみディスクからロード）

if 'initialized' not in st.session_state:
st.session_state.tasks = [Task.from_dict(d) for d in load_tasks_from_disk()]
st.session_state.current_week = datetime.now().date()
st.session_state.image_modal_open = False
st.session_state.image_modal = None
st.session_state.edit_task_id = None
st.session_state.initialized = True


ユーティリティ

def get_week_dates(start_date):
monday = start_date - timedelta(days=start_date.weekday())
return [monday + timedelta(days=i) for i in range(7)]


def format_date_jp(date):
weekdays = ['月', '火', '水', '木', '金', '土', '日']
return f"{date.month}/{date.day}({weekdays[date.weekday()]})"


def get_tasks_for_date(date_str):
return [task for task in st.session_state.tasks if task.date == date_str]


def save_task(task):
idx = next((i for i, t in enumerate(st.session_state.tasks) if t.id == task.id), None)
task.updated_at = datetime.now()
if idx is not None:
st.session_state.tasks[idx] = task
else:
st.session_state.tasks.append(task)
persist_tasks_to_disk([t.to_dict() for t in st.session_state.tasks])


def delete_task(task_id):
st.session_state.tasks = [t for t in st.session_state.tasks if t.id != task_id]
persist_tasks_to_disk([t.to_dict() for t in st.session_state.tasks])


def process_uploaded_image(uploaded_file):
if uploaded_file is not None:
data = uploaded_file.read()
b64 = base64.b64encode(data).decode()
return {
'id': str(uuid.uuid4()),
'name': uploaded_file.name,
'type': uploaded_file.type,
'size': len(data),
'data': f"data:{uploaded_file.type};base64,{b64}"
}
return None


HTMLダッシュボード

def generate_week_html(week_dates):
weekdays_jp = ['月曜日','火曜日','水曜日','木曜日','金曜日','土曜日','日曜日']
css = """

"""
ws, we = week_dates[0].strftime("%Y/%m/%d"), week_dates[6].strftime("%Y/%m/%d")
html = [css, '

', f'
📅 {ws} - {we}
', '
']
for i, date in enumerate(week_dates):
ds = date.strftime("%Y-%m-%d")
tasks = get_tasks_for_date(ds)
html.append('
')
html.append(f'
{weekdays_jp[i]}
')
html.append(f'
{format_date_jp(date)}
')
if not tasks:
html.append('
タスクなし
')
else:
for t in tasks:
pclass = t.priority; ptext = {'high':'高','medium':'中','low':'低'}[t.priority]
html.append(f'
')
html.append(f'
{t.title} {ptext}
')
if t.description: html.append(f'
{t.description}
')
if t.labels:
labels = ''.join([f'{lb}' for lb in t.labels])
html.append(f'
{labels}
')
if t.attachments:
for att in t.attachments:
if att['type'].startswith('image/'): html.append(f'<img class="thumb" src="{att["data"]}" alt="{att["name"]}"/>')
html.append('
')
html.append('
')
html.append('
')
return ''.join(html)

D&D用

def build_short_ids(tasks):
used, mapping = set(), {}
for t in tasks:
base = t.id.replace('-', '')
length = 6
sid = base[:length]
while sid in used and length < len(base):
length += 1; sid = base[:length]
used.add(sid); mapping[t.id] = sid
return mapping


def week_signature(week_dates):
keys = {d.strftime("%Y-%m-%d") for d in week_dates}
items = [(t.id, t.date, t.updated_at.isoformat()) for t in st.session_state.tasks if t.date in keys]
items.sort()
return hashlib.md5(json.dumps(items, ensure_ascii=False).encode("utf-8")).hexdigest()[:10]


st.modal のフォールバック（古い版や互換問題を回避）

@contextmanager
def modal_or_expander(title: str, key: str):
if hasattr(st, "modal"):
with st.modal(title, key=key):
yield
else:
with st.expander(title, expanded=True):
yield


def render_dnd_board(week_dates):
if not SORTABLE_AVAILABLE:
st.info("ドラッグ＆ドロップを使うには requirements.txt に 'streamlit-sortables' を追加してください。")
return


st.markdown("#### 🧲 ドラッグ＆ドロップでタスクを曜日移動")

date_keys = [d.strftime("%Y-%m-%d") for d in week_dates]
all_week_tasks = [t for ds in date_keys for t in get_tasks_for_date(ds)]
short_ids = build_short_ids(all_week_tasks)
short_to_full = {v: k for k, v in short_ids.items()}

containers_payload = []
for ds, d in zip(date_keys, week_dates):
    items = [f"{t.title} [id:{short_ids[t.id]}]" for t in get_tasks_for_date(ds)]
    containers_payload.append({"header": f"{format_date_jp(d)}（{len(items)}）", "items": items})

# バージョン差に対応した可変引数（key は渡さない → 一部版での"key: ..."表示を回避）
kwargs = {"multi_containers": True, "direction": "horizontal"}
try:
    params = inspect.signature(sort_items).parameters
    if "styles" in params:
        kwargs["styles"] = {"container": {"minHeight": "220px", "backgroundColor":"#f8fafc", "border":"2px dashed #e2e8f0",
                                          "borderRadius":"10px", "padding":"8px", "margin":"6px"},
                            "item": {"padding":"6px 10px", "margin":"4px 0", "backgroundColor":"#fff",
                                     "border":"1px solid #e5e7eb", "borderRadius":"8px", "cursor":"grab"}}
    elif "container_style" in params and "item_style" in params:
        kwargs["container_style"] = {"minHeight": "220px", "backgroundColor":"#f8fafc", "border":"2px dashed #e2e8f0",
                                     "borderRadius":"10px", "padding":"8px", "margin":"6px"}
        kwargs["item_style"] = {"padding":"6px 10px", "margin":"4px 0", "backgroundColor":"#fff",
                                "border":"1px solid #e5e7eb", "borderRadius":"8px", "cursor":"grab"}
except Exception:
    pass

new_containers = sort_items(containers_payload, **kwargs)

# [id:xxxx] を抽出して ID→日付に変換
id_to_new_date, pattern = {}, re.compile(r"\[id:([0-9a-fA-F]+)\]\s*$")
for idx, cont in enumerate(new_containers):
    ds = date_keys[idx] if idx < len(date_keys) else None
    if ds is None: continue
    items_list = cont.get("items") if isinstance(cont, dict) else (cont if isinstance(cont, list) else [])
    for label in items_list:
        s = label.get("content") if isinstance(label, dict) else str(label)
        m = pattern.search(s)
        if not m: continue
        short = m.group(1)
        full = short_to_full.get(short)
        if full: id_to_new_date[full] = ds

changed = False
for task in st.session_state.tasks:
    new_date = id_to_new_date.get(task.id)
    if new_date and new_date != task.date:
        task.date = new_date
        task.updated_at = datetime.now()
        changed = True

if changed:
    persist_tasks_to_disk([t.to_dict() for t in st.session_state.tasks])
    st.success("タスクの日付を更新しました。")
    st.rerun()

モーダル制御（画像拡大）

def open_image_modal(attachment):
st.session_state.image_modal = attachment
st.session_state.image_modal_open = True


def close_image_modal():
st.session_state.image_modal = None
st.session_state.image_modal_open = False


編集モーダル

def open_edit_modal(task_id: str):
st.session_state.edit_task_id = task_id


def close_edit_modal():
st.session_state.edit_task_id = None


def render_edit_modal():
tid = st.session_state.edit_task_id
if not tid:
return
task = next((t for t in st.session_state.tasks if t.id == tid), None)
if not task:
close_edit_modal()
return


with modal_or_expander("タスクを編集", key=f"edit_modal_{tid}"):
    with st.form(f"edit_form_{tid}"):
        col1, col2 = st.columns([2, 1])
        with col1:
            new_title = st.text_input("タスクタイトル *", value=task.title)
            new_desc = st.text_area("説明", value=task.description)
        with col2:
            base_date = datetime.now().date()
            try:
                if task.date:
                    base_date = datetime.strptime(task.date, "%Y-%m-%d").date()
            except Exception:
                pass
            new_date = st.date_input("日付", value=base_date, key=f"edit_date_{tid}")
            new_pri = st.selectbox("優先度", ["low", "medium", "high"],
                                   index=["low","medium","high"].index(task.priority if task.priority in ["low","medium","high"] else "medium"),
                                   key=f"edit_pri_{tid}")
            new_labels_str = st.text_input("ラベル (カンマ区切り)", value=",".join(task.labels), key=f"edit_labels_{tid}")
            clear_attachments = st.checkbox("既存の添付を全削除", value=False, key=f"edit_clear_{tid}")
        st.markdown("新しい画像を追加（任意）")
        new_upload = st.file_uploader("画像を追加", type=['png', 'jpg', 'jpeg', 'gif'], key=f"edit_upload_{tid}")
        submitted = st.form_submit_button("保存")

    cancel = st.button("キャンセル", key=f"cancel_edit_{tid}")

    if cancel:
        close_edit_modal()
        st.rerun()

    if submitted:
        task.title = (new_title or task.title).strip()
        task.description = new_desc
        task.date = new_date.strftime("%Y-%m-%d")
        task.priority = new_pri
        task.labels = [s.strip() for s in new_labels_str.split(",") if s.strip()]
        if clear_attachments:
            task.attachments = []
        if new_upload:
            att = process_uploaded_image(new_upload)
            if att:
                task.attachments.append(att)
        save_task(task)
        close_edit_modal()
        st.success("タスクを更新しました。")
        st.rerun()

メインアプリ

def main():
st.markdown('

📅 週間タスクスケジューラー
', unsafe_allow_html=True)

# サイドバー
with st.sidebar:
    st.header("⚙️ 設定")
    week_start = st.date_input("週を選択", value=st.session_state.current_week, key="week_selector")
    st.session_state.current_week = week_start

    st.subheader("📊 タスク統計（全体）")
    total_tasks = len(st.session_state.tasks)
    high_priority = len([t for t in st.session_state.tasks if t.priority == 'high'])
    st.metric("総タスク数", total_tasks)
    st.metric("高優先度", high_priority)

    st.subheader("💾 データ管理")
    if st.session_state.tasks:
        data = json.dumps([t.to_dict() for t in st.session_state.tasks], ensure_ascii=False, indent=2)
        st.download_button("📥 JSONダウンロード", data=data, file_name=f"tasks_{datetime.now().strftime('%Y%m%d')}.json", mime="application/json")

    st.subheader("🖼️ HTMLダッシュボード")
    week_dates_sb = get_week_dates(st.session_state.current_week)
    html_data = generate_week_html(week_dates_sb)
    st.download_button("📤 HTMLダウンロード", data=html_data, file_name=f"tasks_dashboard_{week_dates_sb[0].strftime('%Y%m%d')}_{week_dates_sb[6].strftime('%Y%m%d')}.html", mime="text/html")

    st.subheader("危険な操作")
    if st.button("🗑️ 全データクリア", type="secondary"):
        if st.checkbox("本当に削除しますか？"):
            st.session_state.tasks = []
            persist_tasks_to_disk([])
            st.rerun()

# 週表示
week_dates = get_week_dates(st.session_state.current_week)
ws, we = week_dates[0].strftime("%Y/%m/%d"), week_dates[6].strftime("%Y/%m/%d")
st.markdown(f'<div class="week-header"><h2>📅 {ws} - {we}</h2></div>', unsafe_allow_html=True)

# D&Dモード
with st.expander("🧲 ドラッグ＆ドロップでタスクを曜日移動（週内タスク）", expanded=False):
    if SORTABLE_AVAILABLE:
        render_dnd_board(week_dates)
    else:
        st.info("この機能を使うには requirements.txt に 'streamlit-sortables' を追加してください。")

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
        uploaded_file = st.file_uploader("画像を添付", type=['png', 'jpg', 'jpeg', 'gif'])
        submitted = st.form_submit_button("💾 タスクを保存")

        if submitted and title.strip():
            labels = [s.strip() for s in labels_input.split(',') if s.strip()]
            attachments = []
            if uploaded_file:
                att = process_uploaded_image(uploaded_file)
                if att:
                    attachments.append(att)
            save_task(Task(
                title=title.strip(),
                description=description,
                date=task_date.strftime("%Y-%m-%d"),
                priority=priority,
                labels=labels,
                attachments=attachments
            ))
            st.success(f"✅ タスク「{title}」を作成しました！")
            st.rerun()

# 週間ビュー（曜日直下にカードを表示）
cols = st.columns(7)
weekdays = ['月曜日', '火曜日', '水曜日', '木曜日', '金曜日', '土曜日', '日曜日']

for date, col, weekday in zip(week_dates, cols, weekdays):
    with col:
        st.markdown(
            f'<div class="day-head"><div class="day-name">{weekday}</div>'
            f'<div class="day-date">{format_date_jp(date)}</div></div>',
            unsafe_allow_html=True
        )
        box = st.container(border=True)
        with box:
            day_tasks = get_tasks_for_date(date.strftime("%Y-%m-%d"))
            if not day_tasks:
                st.caption("タスクなし")
            else:
                for task in day_tasks:
                    pcls = f"{task.priority}"
                    badge_cls = f"priority-badge priority-{task.priority}"
                    st.markdown(f'<div class="task-card {pcls}">', unsafe_allow_html=True)

                    # タイトルとアクション
                    c1, c2 = st.columns([5, 1])
                    with c1:
                        st.markdown(f'<div class="task-title">{task.title}</div>', unsafe_allow_html=True)
                        if task.priority != 'medium':
                            ptxt = {'high': '高', 'medium': '中', 'low': '低'}[task.priority]
                            st.markdown(f'<span class="{badge_cls}">{ptxt}</span>', unsafe_allow_html=True)
                    with c2:
                        ec, dc = st.columns(2)
                        with ec:
                            if st.button("✏️", key=f"edit_{task.id}", help="編集"):
                                open_edit_modal(task.id)
                                st.rerun()
                        with dc:
                            if st.button("🗑️", key=f"delete_{task.id}", help="削除"):
                                delete_task(task.id)
                                st.rerun()

                    if task.description:
                        st.markdown(f'<div class="desc">{task.description}</div>', unsafe_allow_html=True)

                    if task.labels:
                        st.markdown(''.join([f'<span class="label-tag">{lb}</span>' for lb in task.labels]), unsafe_allow_html=True)

                    # 画像（クリックで拡大表示）
                    if task.attachments:
                        st.markdown("**📎 添付ファイル:**")
                        for att in task.attachments:
                            if att['type'].startswith('image/'):
                                if CLICKABLE_AVAILABLE:
                                    clicked = clickable_images(
                                        [att['data']], titles=[att['name']],
                                        div_style={"display":"inline-block","padding":"2px"},
                                        img_style={"margin":"4px","height":"110px","border":"1px solid #e5e7eb","border-radius":"6px"},
                                        key=f"thumb_{task.id}_{att['id']}"
                                    )
                                    if clicked == 0:
                                        open_image_modal(att)
                                        st.rerun()
                                else:
                                    try:
                                        b = base64.b64decode(att['data'].split(',')[1])
                                        img = Image.open(io.BytesIO(b))
                                        st.image(img, caption=att['name'], width=140)
                                    except Exception as e:
                                        st.error(f"画像の表示エラー: {str(e)}")
                                    if st.button("🔍", key=f"view_{task.id}_{att['id']}", help="拡大表示"):
                                        open_image_modal(att)
                                        st.rerun()

                    st.markdown('</div>', unsafe_allow_html=True)  # .task-card

# 編集モーダル
render_edit_modal()

# 画像プレビューモーダル
if st.session_state.image_modal_open and st.session_state.image_modal:
    with modal_or_expander("画像プレビュー", key="image_modal"):
        att = st.session_state.image_modal
        st.image(att['data'], caption=att.get('name', ''), use_column_width=True)
        if st.button("閉じる", key="close_image_modal_btn"):
            close_image_modal()
            st.rerun()

if name == "main":
main()

