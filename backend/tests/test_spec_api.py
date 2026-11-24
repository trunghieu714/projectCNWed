"""Kiểm thử bộ API theo đặc tả (POST /api/<tên_api>) và các ràng buộc nghiệp vụ trong slide đề tài."""
import random

from fastapi.testclient import TestClient

from main import app
from tests.helpers import make_video_bytes

client = TestClient(app)
VIDEO = make_video_bytes(seed=11)
VIDEO_2 = make_video_bytes(seed=12)

def api(name, token=None, files=None, **data):
    if token:
        data["token"] = token
    return client.post(f"/api/{name}", data={k: str(v) for k, v in data.items() if v is not None}, files=files)

def phone():
    return "09" + "".join(random.choice("0123456789") for _ in range(8))

def register(role, username):
    ph = phone()
    r = api("signup", phonenumber=ph, password="abc12345", role=role, uuid="dev-1")
    assert r.status_code == 200, r.text
    code = r.json()["data"]["verify_code"]
    r = api("check_verify_code", phonenumber=ph, code_verify=code)
    assert r.json()["code"] == "1000", r.text
    token = r.json()["data"]["token"]
    r = api("change_info_after_signup", token, username=username, height=172)
    assert r.json()["code"] == "1000", r.text
    r = api("login", phonenumber=ph, password="abc12345", uuid="dev-1")
    assert r.json()["code"] == "1000"
    data = r.json()["data"]
    return {"id": data["id"], "token": data["token"], "phone": ph}

def video(name="v.mp4", content=None):
    return (name, content or VIDEO, "video/mp4")

def suffix():
    return random.randint(1000, 999999)

# ---------------------------------------------------------------------------------------------- đăng ký
def test_signup_validation_and_session():
    r = api("signup", phonenumber="12345", password="abc12345")
    assert r.json()["code"] == "1004" and r.json()["message"] == "Số điện thoại không đúng định dạng."
    ph = phone()
    assert api("signup", phonenumber=ph, password="abc@123!").json()["code"] == "1004"   # ký tự đặc biệt
    assert api("signup", phonenumber=ph, password=ph).json()["code"] == "1004"           # trùng SĐT

    r = api("signup", phonenumber=ph, password="abc12345", role="HV")
    code = r.json()["data"]["verify_code"]
    # Chưa xác thực thì không đăng nhập được
    assert api("login", phonenumber=ph, password="abc12345").json()["code"] == "9995"
    assert api("check_verify_code", phonenumber=ph, code_verify="000000" if code != "000000" else "111111").json()["code"] == "1004"
    assert api("check_verify_code", phonenumber=ph).json()["code"] == "1002"
    ok = api("check_verify_code", phonenumber=ph, code_verify=code).json()
    assert ok["code"] == "1000" and ok["data"]["token"]
    # Xác thực lại lần nữa -> đã kích hoạt
    assert api("check_verify_code", phonenumber=ph, code_verify=code).json()["code"] in ("9996", "1004")

    first = api("login", phonenumber=ph, password="abc12345", uuid="phone-A").json()["data"]
    assert first["avatar"] == "-1"  # chưa đổi tên/chiều cao
    second = api("login", phonenumber=ph, password="abc12345", uuid="phone-B").json()["data"]
    # Đăng nhập máy khác: token cũ hết hiệu lực + có thông báo
    assert api("get_notification", first["token"]).json()["code"] == "9998"
    notes = api("get_notification", second["token"]).json()["data"]["notifications"]
    assert any(n["type"] == "login_other_device" for n in notes)
    assert api("change_info_after_signup", second["token"], username="ab$cd", height=170).json()["code"] == "1004"
    assert api("change_info_after_signup", second["token"], username=ph, height=170).json()["code"] == "1004"
    assert api("logout", second["token"]).json()["code"] == "1000"
    assert api("get_notification", second["token"]).json()["code"] == "9998"

# ---------------------------------------------------------------------------------------------- luồng chính
def test_full_exercise_flow():
    s = suffix()
    gv = register("GV", f"gv{s}")
    hv = register("HV", f"hv{s}")

    # GV đăng video chuẩn -> trở thành bài tập, hashtag ở đầu bài viết
    r = api("add_post", gv["token"], files={"left_video": video()}, described="Múa Hồ Thiên Nga phần 1")
    assert r.json()["code"] == "1000", r.text
    ex_post_id = r.json()["data"]["id"]
    post = api("get_post", gv["token"], id=ex_post_id).json()["data"]
    assert post["is_exercise"] and post["described"].startswith(f"#course_{gv['id']} #exercise_{ex_post_id}")
    assert post["video"][0]["thumb"]

    # HV chưa được duyệt vào khóa -> không nộp được
    r = api("add_post", hv["token"], files={"left_video": video("hv.mp4", VIDEO_2)},
            course_id=gv["id"], exercise_id=ex_post_id, described="Bài nộp")
    assert r.json()["code"] == "1009"

    assert api("set_request_course", hv["token"], course_id=gv["id"]).json()["data"]["status"] == "PENDING"
    assert api("set_request_course", hv["token"], course_id=gv["id"]).json()["code"] == "1010"
    reqs = api("get_requested_enrollment", gv["token"]).json()["data"]
    assert [u["id"] for u in reqs] == [hv["id"]]
    assert api("set_approve_enrollment", gv["token"], user_id=hv["id"], is_accept=1).json()["data"]["status"] == "APPROVED"
    students = api("get_list_students", gv["token"], course_id=gv["id"]).json()["data"]
    assert students["total"] == 1

    # Feed của HV ưu tiên bài của khóa đã đăng ký
    other = register("GV", f"gvx{s}")
    api("add_post", other["token"], described="Bài của GV khác đăng sau")
    feed = api("get_list_posts", hv["token"], index=0, count=10).json()["data"]["posts"]
    assert feed[0]["id"] == ex_post_id

    # HV nộp 2 video -> ghép video, chấm 2 góc, bot comment kèm điểm + HTML chi tiết lỗi
    r = api("add_post", hv["token"], files={"left_video": video("l.mp4", VIDEO), "right_video": video("r.mp4", VIDEO_2)},
            course_id=gv["id"], exercise_id=ex_post_id, described="Em nộp bài", device_master="m1", device_slave="s1")
    assert r.json()["code"] == "1000", r.text
    sub_post_id, sub_id = r.json()["data"]["id"], r.json()["data"]["submission_id"]
    assert sub_id
    sub_post = api("get_post", hv["token"], id=sub_post_id).json()["data"]
    assert sub_post["video_fused_url"] and len(sub_post["video"]) == 2
    assert sub_post["lecturer"]["id"] == gv["id"] and sub_post["exercise_id"] == ex_post_id
    assert f"#course_{gv['id']}" in sub_post["described"] and f"#exercise_{ex_post_id}" in sub_post["described"]

    comments = api("get_comment", hv["token"], id=sub_post_id).json()["data"]
    bot = [c for c in comments if c["is_bot_evaluation"]]
    assert bot and bot[0]["score"] is not None
    assert "Bên Trái" in bot[0]["detail_mistakes"] and "Bên Phải" in bot[0]["detail_mistakes"]
    # Video bên trái giống hệt video mẫu của GV -> 100 điểm cho góc trái
    detail = api("get_submission", hv["token"], id=sub_id).json()["data"]
    assert detail["status"] == "COMPLETED" and detail["detail"]["sides"]["left"]["final_score"] == 100.0
    assert detail["report_html_url"].endswith("report.html")
    assert any(n["type"] == "score" for n in api("get_notification", hv["token"]).json()["data"]["notifications"])

    # GV không sửa / xóa được bài tập khi đã có HV nộp
    assert api("edit_post", gv["token"], id=ex_post_id, described="sửa").json()["code"] == "1010"
    assert api("delete_post", gv["token"], id=ex_post_id).json()["code"] == "1009"

    # GV khác nộp bài tập của GV này -> đăng được nhưng không chấm
    r = api("add_post", other["token"], files={"left_video": video()}, exercise_id=ex_post_id, described="thử")
    assert r.json()["code"] == "1000" and r.json()["data"]["submission_id"] is None

def test_edit_post_video_indices_rules():
    hv = register("HV", f"hve{suffix()}")
    post_id = api("add_post", hv["token"], files={"left_video": video()}, described="bài 1").json()["data"]["id"]
    # Bổ sung video vào bên còn trống (không cần video_indices)
    r = api("edit_post", hv["token"], files={"right_video": video("r.mp4", VIDEO_2)}, id=post_id)
    assert r.json()["code"] == "1000"
    p = api("get_post", hv["token"], id=post_id).json()["data"]
    assert p["video_right_url"] and p["video_fused_url"] and p["edited_times"] == 1
    # Test case 6/7: xóa video mà không gửi video thay thế
    assert api("edit_post", hv["token"], id=post_id, video_indices="LR",
               files={"left_video": video()}).json()["code"] == "1002"
    # Test case 9: upload mà không nói rõ video nào bị thay, không có trường hợp lệ khác
    assert api("edit_post", hv["token"], id=post_id, files={"left_video": video()}).json()["code"] == "1004"
    # Test case 8: yêu cầu thay video trái nhưng lại upload video phải
    assert api("edit_post", hv["token"], id=post_id, video_indices="L",
               files={"right_video": video()}).json()["code"] == "1002"
    assert api("edit_post", hv["token"], id=post_id, video_indices="X").json()["code"] == "1004"
    old_left = p["video_left_url"]
    assert api("edit_post", hv["token"], id=post_id, video_indices="L", files={"left_video": video()}).json()["code"] == "1000"
    assert api("get_post", hv["token"], id=post_id).json()["data"]["video_left_url"] != old_left
    # Người khác không sửa được; HV xóa được bài của mình
    other = register("HV", f"hvo{suffix()}")
    assert api("edit_post", other["token"], id=post_id, described="x").json()["code"] == "1009"
    assert api("delete_post", hv["token"], id=post_id).json()["code"] == "1000"
    assert api("get_post", hv["token"], id=post_id).json()["code"] == "9992"

def test_upload_and_text_limits():
    hv = register("HV", f"hvl{suffix()}")
    short = make_video_bytes(seconds=4)
    assert api("add_post", hv["token"], files={"left_video": video("s.mp4", short)}).json()["code"] == "1004"
    assert api("add_post", hv["token"], files={"left_video": ("a.txt", b"abc", "text/plain")}).json()["code"] == "1007"
    assert api("add_post", hv["token"], described=" ".join(["từ"] * 501)).json()["code"] == "1004"
    assert api("add_post", hv["token"]).json()["code"] == "1002"
    pid = api("add_post", hv["token"], described="ok").json()["data"]["id"]
    assert api("set_comment", hv["token"], id=pid, comment=" ".join(["a"] * 501)).json()["code"] == "1004"
    # Chỉ tài khoản chấm điểm mới gửi được score
    assert api("set_comment", hv["token"], id=pid, comment="hi", score=90).json()["code"] == "1009"
    out = api("set_comment", hv["token"], id=pid, comment="<b>Xin chào</b> https://x.vn :)").json()
    assert out["code"] == "1000" and out["data"][-1]["comment"] == "Xin chào https://x.vn :)"
    assert api("get_post", hv["token"], id=99999999).json()["code"] == "9992"
    assert api("get_post", hv["token"], id="abc").json()["code"] == "1003"

def test_like_report_search_block_chat():
    s = suffix()
    a = register("HV", f"hva{s}")
    b = register("GV", f"gvb{s}")
    pid = api("add_post", b["token"], described="Bài múa Hồ Thiên Nga cho người mới").json()["data"]["id"]

    assert api("like", a["token"], id=pid).json()["data"] == {"like": 1, "is_liked": True}
    assert api("like", a["token"], id=pid).json()["data"] == {"like": 0, "is_liked": False}
    api("like", a["token"], id=pid)
    assert api("get_post", a["token"], id=pid).json()["data"]["is_liked"] is True
    assert api("report_post", a["token"], id=pid, subject="Spam", details="...").json()["code"] == "1000"
    assert api("report_post", a["token"], id=pid, subject="Spam").json()["code"] == "1010"

    found = api("search", a["token"], keyword="Nga thiên hồ múa").json()["data"]
    assert any(p["id"] == pid for p in found)
    assert api("get_saved_search", a["token"]).json()["data"][0]["keyword"] == "Nga thiên hồ múa"
    assert api("del_saved_search", a["token"], all=1).json()["code"] == "1000"

    msg = api("set_conversation", a["token"], partner_id=b["id"], content="Chào thầy").json()
    assert msg["code"] == "1000"
    convs = api("get_list_conversation", b["token"]).json()["data"]
    assert convs["numNewMessage"] == 1 and convs["conversations"][0]["partner"]["id"] == a["id"]
    api("set_read_message", b["token"], partner_id=a["id"])
    assert api("get_list_conversation", b["token"]).json()["data"]["numNewMessage"] == 0
    assert api("get_conversation", b["token"], partner_id=a["id"]).json()["data"]["conversation"][0]["message"] == "Chào thầy"

    # HV vào khóa của GV rồi chặn GV -> rời khóa, không xem trang / bài, không nhắn tin được
    api("set_request_course", a["token"], course_id=b["id"])
    api("set_approve_enrollment", b["token"], user_id=a["id"], is_accept=1)
    assert api("set_block", a["token"], user_id=b["id"], type=0).json()["code"] == "1000"
    assert api("set_block", a["token"], user_id=b["id"], type=0).json()["code"] == "1010"
    assert api("get_list_students", b["token"]).json()["data"]["total"] == 0
    assert api("get_user_info", a["token"], user_id=b["id"]).json()["code"] == "1009"
    assert api("get_user_info", b["token"], user_id=a["id"]).json()["code"] == "1009"
    feed_ids = [p["id"] for p in api("get_list_posts", a["token"], count=50).json()["data"]["posts"]]
    assert pid not in feed_ids
    assert api("set_conversation", b["token"], partner_id=a["id"], content="?").json()["code"] == "1009"
    assert api("get_list_blocks", a["token"]).json()["data"]["total"] == 1
    assert api("set_block", a["token"], user_id=b["id"], type=1).json()["code"] == "1000"
    assert api("get_user_info", a["token"], user_id=b["id"]).json()["code"] == "1000"

    types = {n["type"] for n in api("get_notification", b["token"]).json()["data"]["notifications"]}
    assert {"like", "message", "enrollment_request"} <= types

def test_push_settings_and_misc():
    a = register("HV", f"hvp{suffix()}")
    assert api("get_push_settings", a["token"]).json()["data"]["sound_mode"] == 1
    r = api("set_push_settings", a["token"], sound_mode=2, like_comment=0).json()
    assert r["data"]["sound_mode"] == 2 and r["data"]["like_comment"] is False
    assert api("set_push_settings", a["token"], sound_mode=5).json()["code"] == "1004"
    assert api("set_devtoken", a["token"], devtype="web", devtoken="abc").json()["code"] == "1000"
    assert api("check_new_version", last_update="0.1").json()["data"]["version"]["require"] == 1
    assert api("change_password", a["token"], password="abc12345", new_password="abc12345").json()["code"] == "1004"
    assert api("change_password", a["token"], password="abc12345", new_password="newpass99").json()["code"] == "1000"
    assert api("get_list_posts", "not-a-token").json()["code"] == "1000"  # khách vẫn xem được
    assert api("like", "not-a-token", id=1).json()["code"] == "9998"

def test_admin_api():
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import User, UserRole
    db = SessionLocal()
    name = f"admin{suffix()}"
    db.add(User(username=name, email=f"{name}@x.vn", hashed_password=get_password_hash("admin123"), role=UserRole.ADMIN))
    db.commit()
    db.close()
    token = api("admin/login", username=name, password="admin123").json()["data"]["token"]
    assert api("admin/stats", token).json()["data"]["users"] >= 1
    users = api("admin/users", token, keyword="hv").json()["data"]["users"]
    if users:
        uid = users[0]["id"]
        assert api("admin/update_user", token, user_id=uid, is_active=0).json()["data"]["is_active"] is False
    hv = register("HV", f"hvz{suffix()}")
    assert api("admin/stats", hv["token"]).json()["code"] == "1009"

def test_feed_keeps_posts_without_course_for_enrolled_student():
    s = suffix()
    gv = register("GV", f"gvf{s}")
    hv = register("HV", f"hvf{s}")
    other = register("HV", f"hvg{s}")
    api("set_request_course", hv["token"], course_id=gv["id"])
    api("set_approve_enrollment", gv["token"], user_id=hv["id"], is_accept=1)
    course_post = api("add_post", gv["token"], described="bài trong khóa").json()["data"]["id"]
    free_post = api("add_post", other["token"], described="bài tự do không thuộc khóa nào").json()["data"]["id"]
    ids = [p["id"] for p in api("get_list_posts", hv["token"], count=100).json()["data"]["posts"]]
    assert course_post in ids and free_post in ids
    assert ids.index(course_post) < ids.index(free_post)  # bài của khóa đã đăng ký được ưu tiên

def test_old_database_gets_new_columns(tmp_path):
    import sqlite3
    from sqlalchemy import create_engine, inspect
    import app.core.database as database
    old = tmp_path / "old.db"
    conn = sqlite3.connect(old)
    conn.execute("CREATE TABLE comments (id INTEGER PRIMARY KEY, post_id INTEGER, user_id INTEGER, content TEXT, is_bot_evaluation BOOLEAN, created_at DATETIME)")
    conn.commit()
    conn.close()
    original = database.engine
    database.engine = create_engine(f"sqlite:///{old.as_posix()}")
    try:
        database.init_db()
        cols = {c["name"] for c in inspect(database.engine).get_columns("comments")}
        assert {"score", "detail_mistakes"} <= cols
        assert "post_likes" in inspect(database.engine).get_table_names()
    finally:
        database.engine.dispose()
        database.engine = original
