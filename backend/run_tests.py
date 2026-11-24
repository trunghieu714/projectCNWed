import sys
import os
import numpy as np

# Đảm bảo đường dẫn import
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

print("=" * 60)
print("TEST 1: KIỂM TRA THUẬT TOÁN DTW & SCORER")
print("=" * 60)
from ai_engine.scorers.dtw_scorer import FastDTWScorer

scorer = FastDTWScorer(angle_tolerance=15.0)

# 1.1 Test chuỗi giống nhau
angles_identical = np.linspace(45.0, 90.0, num=150, dtype=np.float32).reshape(30, 5)
res_ident = scorer.evaluate({"joint_angles": angles_identical}, {"joint_angles": angles_identical})
print(f"[*] Test 1.1 (Chuỗi giống hệt nhau): Điểm = {res_ident['final_score']}/100, Lỗi = {len(res_ident['frame_errors'])}")
assert res_ident['final_score'] == 100.0, "Điểm phải bằng 100.0!"
assert len(res_ident['frame_errors']) == 0, "Không được có lỗi!"

# 1.2 Test phát hiện sai lệch góc
angles_coach = np.full((30, 5), 90.0, dtype=np.float32)
angles_student = np.full((30, 5), 90.0, dtype=np.float32)
angles_student[10:15, :] += 30.0  # Tạo độ lệch 30 độ
res_dev = scorer.evaluate({"joint_angles": angles_coach}, {"joint_angles": angles_student})
print(f"[*] Test 1.2 (Chuỗi có sai lệch 30°): Điểm = {res_dev['final_score']}/100, Số frame lỗi = {len(res_dev['frame_errors'])}")
assert res_dev['final_score'] < 100.0, "Điểm phải bị trừ do có sai lệch!"
assert len(res_dev['frame_errors']) > 0, "Phải phát hiện được frame sai lệch!"

# 1.3 Test dữ liệu rỗng
res_empty = scorer.evaluate({"joint_angles": []}, {"joint_angles": []})
print(f"[*] Test 1.3 (Dữ liệu rỗng): Điểm = {res_empty['final_score']}, Phản hồi = '{res_empty['feedback_summary']}'")
assert res_empty['final_score'] == 0.0

print("\n" + "=" * 60)
print("TEST 2: KIỂM TRA TCPFORMER ADAPTER & MOCK ESTIMATOR")
print("=" * 60)
from ai_engine.factory import AIEngineFactory

tcp_adapter = AIEngineFactory.create_estimator("tcpformer")
poses_tcp = tcp_adapter.extract_poses("dummy_video.mp4")
print(f"[*] TCPFormerAdapter trích xuất: {poses_tcp['total_frames']} frames, shape joint angles = {poses_tcp['joint_angles'].shape}")
assert poses_tcp['total_frames'] > 0
assert poses_tcp['joint_angles'].shape[1] == 5

mock_estimator = AIEngineFactory.create_estimator("mock")
poses_mock = mock_estimator.extract_poses("dummy_video.mp4")
print(f"[*] MockPoseEstimator trích xuất: {poses_mock['total_frames']} frames, shape joint angles = {poses_mock['joint_angles'].shape}")
assert poses_mock['total_frames'] == 60

print("\n" + "=" * 60)
print("TEST 3: KIỂM TRA TOÀN DIỆN AI PIPELINE (FACADE PATTERN)")
print("=" * 60)
from ai_engine.pipeline import SkillAssessmentPipeline

pipeline = SkillAssessmentPipeline(
    estimator=tcp_adapter,
    scorer=scorer,
    visualizer=AIEngineFactory.create_visualizer("fused_video")
)

test_output_dir = os.path.join("storage", "test_outputs")
pipeline_res = pipeline.run_assessment(
    coach_video_path="storage/coach_samples/mock_coach.mp4",
    student_video_path="storage/coach_samples/mock_student.mp4",
    output_dir=test_output_dir
)

print(f"[*] Điểm đánh giá AI: {pipeline_res['score']}/100")
print(f"[*] Nhận xét tóm tắt: {pipeline_res['summary']}")
print(f"[*] Độ dài đường đi Warping Path: {pipeline_res['warping_path_length']}")
print(f"[*] Video kết quả đã render: {pipeline_res['fused_video_url']}")
assert os.path.exists(pipeline_res['fused_video_url']), "File video fused_output.mp4 phải tồn tại!"
print(f"[*] Kích thước file video output: {os.path.getsize(pipeline_res['fused_video_url'])} bytes")

print("\n" + "=" * 60)
print(">>> TẤT CẢ CÁC BÀI TEST AI ENGINE & PIPELINE ĐỀU PASS THÀNH CÔNG 100%!")
print("=" * 60)
