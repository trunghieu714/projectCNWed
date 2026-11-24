import os
import pytest
from ai_engine.factory import AIEngineFactory
from ai_engine.pipeline import SkillAssessmentPipeline

def test_pipeline_with_mock():
    """Kiểm tra Pipeline thực thi trơn tru với Mock Pose Estimator và Fused Video Renderer."""
    estimator = AIEngineFactory.create_estimator("mock")
    scorer = AIEngineFactory.create_scorer("dtw")
    visualizer = AIEngineFactory.create_visualizer("fused_video")
    
    pipeline = SkillAssessmentPipeline(
        estimator=estimator,
        scorer=scorer,
        visualizer=visualizer
    )
    
    output_dir = "storage/test_outputs"
    os.makedirs(output_dir, exist_ok=True)
    
    result = pipeline.run_assessment(
        coach_video_path="mock_coach.mp4",
        student_video_path="mock_student.mp4",
        output_dir=output_dir
    )
    
    assert "score" in result
    assert "summary" in result
    assert "fused_video_url" in result
    assert result["score"] >= 0.0
