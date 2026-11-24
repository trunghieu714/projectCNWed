from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseVisualizer(ABC):
    """
    Abstract Base Class cho các module xuất kết quả trực quan (Visualizer).
    Phụ trách việc render video so sánh (fused_output.mp4) hoặc sinh heatmap sai lệch.
    """

    @abstractmethod
    def render_fused_video(
        self,
        coach_video_path: str,
        student_video_path: str,
        evaluation_result: Dict[str, Any],
        output_video_path: str
    ) -> str:
        """
        Ghép và vẽ khung xương HLV và HV song song (side-by-side) hoặc chồng (overlay)
        kèm màu sắc cảnh báo đúng/sai theo nhịp DTW.

        Returns:
            output_video_path: Đường dẫn video kết quả đã xuất thành công.
        """
        pass
