/* Trình xem khung xương 3D HLV - HV trong báo cáo HTML (không dùng thư viện ngoài).
   Mỗi khối .sk3d chứa: <script type="application/json"> dữ liệu, <canvas>, thanh tua, nút phát, chọn chế độ. */
(function () {
  var COACH = "#1877f2", STUDENT = "#2e7d32", BAD = "#c62828", GRID = "#d0d4da";

  function setup(root) {
    var data = JSON.parse(root.querySelector("script[type='application/json']").textContent);
    var frames = data.frames, bones = data.bones, tol = data.tolerance, names = data.names;
    var canvas = root.querySelector("canvas"), ctx = canvas.getContext("2d");
    var slider = root.querySelector(".sk-slider"), playBtn = root.querySelector(".sk-play");
    var modeSel = root.querySelector(".sk-mode"), info = root.querySelector(".sk-info");
    var yaw = -0.6, pitch = 0.2, zoom = 1, idx = 0, playing = true, lastStep = 0;
    var floorY = Infinity;
    frames.forEach(function (f) { f.c.forEach(function (p) { floorY = Math.min(floorY, p[1]); }); });
    slider.max = String(frames.length - 1);

    // shift: dịch trên màn hình (tỉ lệ chiều rộng) để chế độ "Cạnh nhau" luôn trái/phải dù xoay góc nhìn
    function project(p, w, h, shift) {
      var x = p[0], y = p[1], z = p[2];
      var cy = Math.cos(yaw), sy = Math.sin(yaw);
      var x1 = cy * x + sy * z, z1 = -sy * x + cy * z;
      var cp = Math.cos(pitch), sp = Math.sin(pitch);
      var y1 = cp * y - sp * z1, z2 = sp * y + cp * z1;
      var d = 6 / (6 + z2), s = Math.min(w * (shift ? 0.5 : 1), h) * 0.26 * zoom;
      return [w * (0.5 + shift) + x1 * d * s, h * 0.55 - y1 * d * s];
    }

    function drawGrid(w, h, offX) {
      ctx.strokeStyle = GRID; ctx.lineWidth = 1;
      for (var g = -2; g <= 2; g++) {
        var a = project([g * 0.5, floorY, -1], w, h, offX), b = project([g * 0.5, floorY, 1], w, h, offX);
        var c = project([-1, floorY, g * 0.5], w, h, offX), d = project([1, floorY, g * 0.5], w, h, offX);
        ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.moveTo(c[0], c[1]); ctx.lineTo(d[0], d[1]); ctx.stroke();
      }
    }

    function drawSkeleton(pts, color, errs, w, h, offX, width) {
      var p2 = pts.map(function (p) { return project(p, w, h, offX); });
      ctx.lineWidth = width; ctx.lineCap = "round"; ctx.strokeStyle = color;
      bones.forEach(function (b) {
        ctx.beginPath(); ctx.moveTo(p2[b[0]][0], p2[b[0]][1]); ctx.lineTo(p2[b[1]][0], p2[b[1]][1]); ctx.stroke();
      });
      p2.forEach(function (q, j) {
        var bad = errs && errs[j] > tol;
        ctx.fillStyle = bad ? BAD : color;
        ctx.beginPath(); ctx.arc(q[0], q[1], bad ? 5 : 3, 0, 2 * Math.PI); ctx.fill();
      });
    }

    function draw() {
      var dpr = window.devicePixelRatio || 1, w = canvas.clientWidth, h = canvas.clientHeight;
      if (!w || !h) return;
      if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
        canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      var f = frames[idx], side = modeSel.value === "side";
      var offC = side ? -0.25 : 0, offS = side ? 0.25 : 0;
      drawGrid(w, h, offC); if (side) drawGrid(w, h, offS);
      if (modeSel.value !== "student") drawSkeleton(f.c, COACH, null, w, h, offC, side ? 3 : 4);
      if (modeSel.value !== "coach") drawSkeleton(f.s, STUDENT, f.e, w, h, offS, 3);
      var mean = f.e.reduce(function (a, b) { return a + b; }, 0) / f.e.length;
      var worst = f.e.map(function (e, j) { return [e, j]; }).filter(function (x) { return x[0] > tol; })
        .sort(function (a, b) { return b[0] - a[0]; }).slice(0, 3)
        .map(function (x) { return names[x[1]] + " " + Math.round(x[0] * 100) + "%"; });
      info.textContent = "Cặp " + (idx + 1) + "/" + frames.length + " · frame HLV " + f.cf + " ↔ frame HV " + f.sf +
        (f.t !== null && f.t !== undefined ? " (" + f.t.toFixed(2) + "s)" : "") +
        " · lệch TB " + Math.round(mean * 100) + "%" + (worst.length ? " · khớp lệch: " + worst.join(", ") : " · không có khớp vượt ngưỡng");
      slider.value = String(idx);
    }

    function loop(ts) {
      if (playing && canvas.clientWidth && ts - lastStep > 80) { idx = (idx + 1) % frames.length; lastStep = ts; draw(); }
      window.requestAnimationFrame(loop);
    }

    var drag = null;
    canvas.addEventListener("pointerdown", function (e) { drag = [e.clientX, e.clientY]; canvas.setPointerCapture(e.pointerId); });
    canvas.addEventListener("pointermove", function (e) {
      if (!drag) return;
      yaw += (e.clientX - drag[0]) * 0.01;
      pitch = Math.max(-1.4, Math.min(1.4, pitch + (e.clientY - drag[1]) * 0.01));
      drag = [e.clientX, e.clientY]; draw();
    });
    canvas.addEventListener("pointerup", function () { drag = null; });
    canvas.addEventListener("wheel", function (e) {
      e.preventDefault(); zoom = Math.max(0.4, Math.min(4, zoom * (e.deltaY < 0 ? 1.1 : 0.9))); draw();
    }, { passive: false });
    slider.addEventListener("input", function () { idx = parseInt(slider.value, 10) || 0; playing = false; playBtn.textContent = "▶ Phát"; draw(); });
    playBtn.addEventListener("click", function () { playing = !playing; playBtn.textContent = playing ? "⏸ Dừng" : "▶ Phát"; });
    modeSel.addEventListener("change", draw);
    window.addEventListener("resize", draw);
    document.querySelectorAll("input[name='side']").forEach(function (r) { r.addEventListener("change", function () { setTimeout(draw, 0); }); });
    draw();
    window.requestAnimationFrame(loop);
  }

  document.querySelectorAll(".sk3d").forEach(setup);
})();
