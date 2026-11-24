import pytest
import numpy as np
from ai_engine.scorers.dtw_scorer import FastDTWScorer

def test_dtw_scorer_identical_sequences():
    """Kiểm tra khi 2 chuỗi động tác giống hệt nhau -> điểm số phải xấp xỉ 100."""
    scorer = FastDTWScorer(angle_tolerance=15.0)
    
    # 30 frames, mỗi frame 5 góc khớp
    angles = np.linspace(45.0, 90.0, num=150).reshape(30, 5)
    
    coach_data = {"joint_angles": angles}
    student_data = {"joint_angles": angles}
    
    result = scorer.evaluate(coach_data, student_data)
    
    assert result["final_score"] == 100.0
    assert len(result["frame_errors"]) == 0
    assert len(result["warping_path"]) == 30

def test_dtw_scorer_detect_deviations():
    """Kiểm tra khả năng bắt lỗi khi góc khớp bị lệch vượt ngưỡng cho phép."""
    scorer = FastDTWScorer(angle_tolerance=10.0)
    
    angles_coach = np.full((20, 5), 90.0)
    angles_student = np.full((20, 5), 90.0)
    
    # Tạo độ lệch 25 độ ở 5 frame giữa
    angles_student[5:10, :] += 25.0
    
    coach_data = {"joint_angles": angles_coach}
    student_data = {"joint_angles": angles_student}
    
    result = scorer.evaluate(coach_data, student_data)
    
    assert result["final_score"] < 100.0
    assert len(result["frame_errors"]) > 0
    assert any(err["max_angle_error"] >= 20.0 for err in result["frame_errors"])

def test_dtw_scorer_empty_input():
    """Kiểm tra xử lý biên khi dữ liệu pose rỗng."""
    scorer = FastDTWScorer()
    result = scorer.evaluate({"joint_angles": []}, {"joint_angles": []})
    
    assert result["final_score"] == 0.0
    assert result["warping_path"] == []
