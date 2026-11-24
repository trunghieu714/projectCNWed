# Pose Grader Cross-view Final V9

This version uses the HieuDV / DungHM sample structure for the final 4 report folders.

Main changes:
- The HTML no longer shows the old DTW explanation sentence.
- Two-video reports show two tabs:
  - Bên Trái
  - Bên Phải
- Each tab only contains the error list for that side.
- Single-video reports are generated from temporary folders where each folder has only one video/pkl pair.
- The visual report keeps reference image and student image separate. It does not draw the reference skeleton on the student image.
- Metric is PA-MPJPE in all final run scripts.

Expected sample folders on Windows:
- E:\PKL_Test\HieuDV
- E:\PKL_Test\DungHM

Run:
```bat
cd /d E:\pose_grader_crossview_final_v9
E:\Fix_pkl_grader\.venv\Scripts\activate
python VERIFY_CROSSVIEW_FIX.py
RUN_CREATE_FINAL_4_REPORTS.cmd
```

Output:
```text
E:\final_reports_to_send
  01_two_video_PA_MPJPE_official
  02_single_video_PA_MPJPE_official
  03_single_video_PA_MPJPE_visual_demo
  04_two_video_PA_MPJPE_visual_demo
```

Notes:
- Official folders use only error rows.
- Visual demo folders may include sampled passing rows so the teacher can inspect the image layout.
- The single-video case is created from the left video/pkl sample by copying it into temporary folders `_single_ref` and `_single_stu`.
