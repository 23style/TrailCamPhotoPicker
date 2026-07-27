document.addEventListener("DOMContentLoaded", () => {
  const checkboxes = Array.from(document.querySelectorAll(".keep-checkbox"));
  const statusText = document.getElementById("statusText");
  const execForm = document.getElementById("execForm");

  function updateStatus() {
    const total = checkboxes.length;
    const kept = checkboxes.filter(cb => cb.checked).length;
    const deleted = total - kept;
    statusText.textContent = `全 ${total} 枚 / 残す ${kept} 枚 / 削除予定 ${deleted} 枚`;
  }

  checkboxes.forEach(cb => cb.addEventListener("change", updateStatus));
  updateStatus();

  const checkAllBtn = document.getElementById("checkAll");
  const uncheckAllBtn = document.getElementById("uncheckAll");
  if (checkAllBtn) {
    checkAllBtn.addEventListener("click", () => {
      checkboxes.forEach(cb => cb.checked = true);
      updateStatus();
    });
  }
  if (uncheckAllBtn) {
    uncheckAllBtn.addEventListener("click", () => {
      checkboxes.forEach(cb => cb.checked = false);
      updateStatus();
    });
  }

  // 作業中のチェック状態をサーバーへ自動保存（デバウンス）
  let saveTimer = null;
  function scheduleSaveState() {
    if (!execForm) return;
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      const folder = execForm.querySelector('input[name="folder"]').value;
      const keep = checkboxes.filter(cb => cb.checked).map(cb => cb.value);
      fetch("/save_state", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ folder, keep }),
      }).catch(() => {});
    }, 500);
  }
  checkboxes.forEach(cb => cb.addEventListener("change", scheduleSaveState));

  // thumbnail size slider
  const thumbSizeSlider = document.getElementById("thumbSizeSlider");
  if (thumbSizeSlider) {
    thumbSizeSlider.addEventListener("input", () => {
      document.documentElement.style.setProperty("--thumb-size", thumbSizeSlider.value + "px");
    });
  }

  // ---- lightbox ----
  const photos = Array.from(document.querySelectorAll(".photo-card")).map(card => ({
    card,
    checkbox: card.querySelector(".keep-checkbox"),
    img: card.querySelector("img.thumb"),
    full: card.querySelector("img.thumb").dataset.full,
    name: card.querySelector(".keep-checkbox").value,
    day: card.closest(".day-group").dataset.day,
  }));

  const dayCounts = {};
  photos.forEach(p => { dayCounts[p.day] = (dayCounts[p.day] || 0) + 1; });
  const dayRunning = {};
  photos.forEach(p => {
    dayRunning[p.day] = (dayRunning[p.day] || 0) + 1;
    p.dayIndex = dayRunning[p.day];
    p.dayTotal = dayCounts[p.day];
  });

  const lightbox = document.getElementById("lightbox");
  const lightboxImg = document.getElementById("lightboxImg");
  const lbPhotoWrap = document.getElementById("lbPhotoWrap");
  const lbTransition = document.getElementById("lbTransition");
  const lbTransitionLabel = document.getElementById("lbTransitionLabel");
  const lbFileName = document.getElementById("lbFileName");
  const lbDayLabel = document.getElementById("lbDayLabel");
  const lbCounter = document.getElementById("lbCounter");
  const lbKeepCheckbox = document.getElementById("lbKeepCheckbox");
  const lbPrev = document.getElementById("lbPrev");
  const lbNext = document.getElementById("lbNext");
  const lbClose = document.getElementById("lbClose");

  let currentIndex = -1;
  let pendingIndex = null;

  function renderPhoto() {
    const p = photos[currentIndex];
    lightboxImg.src = p.full;
    lbFileName.textContent = p.name;
    lbDayLabel.textContent = p.day;
    lbCounter.textContent = `${p.dayIndex} / ${p.dayTotal}枚`;
    lbKeepCheckbox.checked = p.checkbox.checked;
    lbTransition.classList.add("hidden");
    lbPhotoWrap.classList.remove("hidden");
    lbPrev.disabled = currentIndex <= 0;
    lbNext.disabled = currentIndex >= photos.length - 1;
  }

  function showTransition(targetIndex) {
    pendingIndex = targetIndex;
    lbTransitionLabel.textContent = photos[targetIndex].day;
    lbTransition.classList.remove("hidden");
    lbPhotoWrap.classList.add("hidden");
  }

  function resolvePending() {
    currentIndex = pendingIndex;
    pendingIndex = null;
    renderPhoto();
  }

  function openLightbox(index) {
    currentIndex = index;
    pendingIndex = null;
    renderPhoto();
    lightbox.classList.remove("hidden");
  }

  function closeLightbox() {
    lightbox.classList.add("hidden");
    lightboxImg.src = "";
    pendingIndex = null;
  }

  function goNext() {
    if (pendingIndex !== null) { resolvePending(); return; }
    if (currentIndex >= photos.length - 1) return;
    const next = currentIndex + 1;
    if (photos[next].day !== photos[currentIndex].day) {
      showTransition(next);
    } else {
      currentIndex = next;
      renderPhoto();
    }
  }

  function goPrev() {
    if (pendingIndex !== null) { resolvePending(); return; }
    if (currentIndex <= 0) return;
    const prev = currentIndex - 1;
    if (photos[prev].day !== photos[currentIndex].day) {
      showTransition(prev);
    } else {
      currentIndex = prev;
      renderPhoto();
    }
  }

  photos.forEach((p, i) => {
    p.img.addEventListener("click", (e) => {
      e.preventDefault();
      openLightbox(i);
    });
  });

  lbTransition.addEventListener("click", resolvePending);
  lbNext.addEventListener("click", goNext);
  lbPrev.addEventListener("click", goPrev);
  lbClose.addEventListener("click", closeLightbox);

  lbKeepCheckbox.addEventListener("change", () => {
    if (currentIndex < 0) return;
    const p = photos[currentIndex];
    p.checkbox.checked = lbKeepCheckbox.checked;
    updateStatus();
  });

  lightbox.addEventListener("click", (e) => {
    if (e.target === lightbox) closeLightbox();
  });

  document.addEventListener("keydown", (e) => {
    if (lightbox.classList.contains("hidden")) return;
    if (e.key === "ArrowRight") goNext();
    else if (e.key === "ArrowLeft") goPrev();
    else if (e.key === "Escape") closeLightbox();
  });

  if (execForm) {
    execForm.addEventListener("submit", (e) => {
      const total = checkboxes.length;
      const deleted = checkboxes.filter(cb => !cb.checked).length;
      const ok = confirm(
        `チェックの入っていない ${deleted} 枚（全 ${total} 枚中）を delete フォルダへ移動します。よろしいですか？`
      );
      if (!ok) e.preventDefault();
    });
  }
});
