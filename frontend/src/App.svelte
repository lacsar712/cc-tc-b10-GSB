<script>
  let session = null;
  let logs = [];
  let loginUser = "surveyor";
  let loginPass = "surv123456";
  let chainage = "";
  let deltaMm = "";
  let error = "";
  let loading = false;
  let timer;
  let view = "desk";

  // 夜间提醒专页状态
  let nightState = null;
  let reminders = [];
  let nightError = "";
  let nightSaving = false;
  let nightTimer;
  let fStart = "22:00";
  let fEnd = "06:00";
  let fWindow = 30;
  let fThreshold = 3;
  let formTouched = false;

  $: isWriter = session?.role === "writer";

  function headers() {
    return session ? { Authorization: "Bearer " + session.token } : {};
  }

  async function refresh() {
    if (!session) return;
    const res = await fetch("/api/logs", { headers: headers() });
    if (res.status === 401) {
      logout();
      return;
    }
    if (res.ok) logs = await res.json();
    // 桌面视图也静默取一次灯状态，用于页眉红点（不影响交单）。
    if (view !== "night") {
      try {
        const nres = await fetch("/api/night/state", { headers: headers() });
        if (nres.ok) nightState = await nres.json();
      } catch {
        /* 灯状态静默失败，不影响测缝 */
      }
    }
  }

  async function refreshNight() {
    if (!session) return;
    const [sres, rres] = await Promise.all([
      fetch("/api/night/state", { headers: headers() }),
      fetch("/api/night/reminders", { headers: headers() }),
    ]);
    if (sres.status === 401 || rres.status === 401) {
      logout();
      return;
    }
    if (sres.ok) {
      nightState = await sres.json();
      // 用户正在编辑时不要用轮询值覆盖其未保存输入。
      if (!formTouched) {
        const s = nightState.setting || {};
        fStart = s.night_start ?? fStart;
        fEnd = s.night_end ?? fEnd;
        fWindow = s.window_minutes ?? fWindow;
        fThreshold = s.low_sample_threshold ?? fThreshold;
      }
    }
    if (rres.ok) reminders = await rres.json();
  }

  function startTimers() {
    refresh();
    timer = setInterval(refresh, 2000);
  }

  async function login() {
    error = "";
    loading = true;
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: loginUser, password: loginPass }),
      });
      const data = await res.json();
      if (!res.ok) {
        error = data.detail || "登录失败";
        return;
      }
      session = { token: data.access_token, username: data.username, role: data.role };
      localStorage.setItem("tunnel_session", JSON.stringify(session));
      startTimers();
    } catch {
      error = "无法连接接口";
    } finally {
      loading = false;
    }
  }

  function logout() {
    if (timer) clearInterval(timer);
    if (nightTimer) clearInterval(nightTimer);
    session = null;
    logs = [];
    nightState = null;
    reminders = [];
    view = "desk";
    localStorage.removeItem("tunnel_session");
  }

  async function submit() {
    error = "";
    loading = true;
    try {
      const res = await fetch("/api/logs", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...headers() },
        body: JSON.stringify({ chainage, delta_mm: Number(deltaMm) }),
      });
      const data = await res.json();
      if (!res.ok) {
        error = data.detail || "提交失败";
        return;
      }
      chainage = "";
      deltaMm = "";
      await refresh();
    } catch {
      error = "提交时网络异常";
    } finally {
      loading = false;
    }
  }

  function gotoView(v) {
    view = v;
    if (nightTimer) clearInterval(nightTimer);
    if (v === "night") {
      formTouched = false;
      refreshNight();
      nightTimer = setInterval(refreshNight, 2000);
    } else {
      refresh();
    }
  }

  async function saveNight() {
    nightError = "";
    nightSaving = true;
    try {
      const res = await fetch("/api/night/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...headers() },
        body: JSON.stringify({
          night_start: fStart,
          night_end: fEnd,
          window_minutes: Number(fWindow),
          low_sample_threshold: Number(fThreshold),
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        nightError = data.detail || "保存失败";
        return;
      }
      nightState = data;
      formTouched = false;
      await refreshNight();
    } catch {
      nightError = "保存时网络异常";
    } finally {
      nightSaving = false;
    }
  }

  async function clearDone() {
    nightError = "";
    nightSaving = true;
    try {
      const res = await fetch("/api/night/clear-done", {
        method: "POST",
        headers: headers(),
      });
      const data = await res.json();
      if (!res.ok) {
        nightError = data.detail || "清空失败";
        return;
      }
      nightState = data;
      await Promise.all([refreshNight(), refresh()]);
    } catch {
      nightError = "清空时网络异常";
    } finally {
      nightSaving = false;
    }
  }

  const raw = localStorage.getItem("tunnel_session");
  if (raw) {
    try {
      session = JSON.parse(raw);
      startTimers();
    } catch {
      localStorage.removeItem("tunnel_session");
    }
  }
</script>

<style>
  :global(body) {
    margin: 0;
    font-family: "Segoe UI", system-ui, sans-serif;
    background: #1c1917;
    color: #f5f5f4;
  }
  main { max-width: 960px; margin: 0 auto; padding: 1.5rem; }
  .topbar { display: flex; align-items: center; justify-content: space-between; gap: 1rem; flex-wrap: wrap; }
  h1 { color: #fbbf24; margin: 0 0 0.25rem; }
  .sub { color: #a8a29e; margin-bottom: 1.25rem; }
  section {
    background: #292524; border: 1px solid #44403c; border-radius: 8px;
    padding: 1rem 1.25rem; margin-bottom: 1rem;
  }
  label { display: block; font-size: 0.85rem; color: #d6d3d1; margin-bottom: 0.25rem; }
  input {
    width: 100%; box-sizing: border-box; padding: 0.5rem 0.65rem; border-radius: 6px;
    border: 1px solid #57534e; background: #0c0a09; color: #fafaf9; margin-bottom: 0.75rem;
  }
  button {
    cursor: pointer; padding: 0.5rem 1rem; border: none; border-radius: 6px;
    background: #d97706; color: #fff; font-weight: 600;
  }
  button.secondary { background: #57534e; }
  button.nav { background: #1d4ed8; position: relative; }
  button.nav .dot {
    position: absolute; top: -5px; right: -5px; width: 12px; height: 12px;
    border-radius: 50%; background: #dc2626; border: 2px solid #1c1917;
    box-shadow: 0 0 8px 2px rgba(220,38,38,0.8);
  }
  .err { color: #fb7185; }
  table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
  th, td { text-align: left; padding: 0.45rem; border-bottom: 1px solid #44403c; vertical-align: top; }
  .tag { padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.8rem; }
  .ok { background: #14532d; color: #86efac; }
  .bad { background: #7f1d1d; color: #fca5a5; }
  .pending { background: #713f12; color: #fde68a; }

  .lamp-row { display: flex; align-items: center; gap: 1rem; }
  .lamp {
    width: 42px; height: 42px; border-radius: 50%; background: #57534e;
    border: 2px solid #78716c; flex: none;
  }
  .lamp.on {
    background: radial-gradient(circle at 35% 30%, #fca5a5, #dc2626);
    border-color: #fecaca; box-shadow: 0 0 18px 4px rgba(220,38,38,0.7);
  }
  .lamp-text.big { font-size: 1.15rem; font-weight: 700; }
  .lamp-on { color: #fca5a5; }
  .lamp-off { color: #a8a29e; }
  .metrics { display: flex; gap: 1.5rem; flex-wrap: wrap; margin-top: 0.5rem; }
  .metric { background: #0c0a09; border: 1px solid #44403c; border-radius: 6px; padding: 0.5rem 0.85rem; }
  .metric .k { font-size: 0.75rem; color: #a8a29e; }
  .metric .v { font-size: 1.2rem; font-weight: 700; }
  .form-grid { display: flex; gap: 1rem; flex-wrap: wrap; }
  .form-grid > div { flex: 1 1 140px; }
  .readonly-note { color: #a8a29e; font-size: 0.85rem; }
  .hint { color: #a8a29e; font-size: 0.8rem; margin-top: -0.4rem; margin-bottom: 0.75rem; }
</style>

<main>
  {#if !session}
    <h1>隧道收敛测缝台</h1>
    <p class="sub">测量员提交桩号与收敛毫米值，接口进程内线程认领后出结论。登录框已预填可写账号 surveyor / surv123456。</p>
    <section>
      <label>用户名</label>
      <input bind:value={loginUser} autocomplete="off" />
      <label>密码</label>
      <input type="password" bind:value={loginPass} autocomplete="off" />
      <button disabled={loading} on:click={login}>登录</button>
      {#if error}<p class="err">{error}</p>{/if}
    </section>
  {:else}
    <div class="topbar">
      <h1>{view === "night" ? "夜间低办结提醒" : "隧道收敛测缝台"}</h1>
      {#if view === "night"}
        <button class="secondary" on:click={() => gotoView("desk")}>← 收敛测缝台</button>
      {:else}
        <button class="nav" on:click={() => gotoView("night")}>
          夜间提醒{#if nightState?.light_on}<span class="dot"></span>{/if}
        </button>
      {/if}
    </div>
    <p class="sub">已登录：{session.username}（{isWriter ? "可提交" : "只读"}）</p>
    <section>
      <button class="secondary" on:click={logout}>退出</button>
      {#if view === "desk"}
        <button class="secondary" disabled={loading} on:click={refresh}>刷新列表</button>
      {:else}
        <button class="secondary" on:click={refreshNight}>刷新提醒</button>
      {/if}
    </section>

    {#if view === "desk"}
      {#if isWriter}
        <section>
          <label>里程桩号</label>
          <input placeholder="例如 K20+050" bind:value={chainage} />
          <label>收敛（毫米，可正可负）</label>
          <input type="number" step="0.1" bind:value={deltaMm} />
          <button disabled={loading} on:click={submit}>提交（进入待认领）</button>
          {#if error}<p class="err">{error}</p>{/if}
        </section>
      {/if}
      <section>
        <table>
          <thead>
            <tr><th>编号</th><th>桩号</th><th>收敛mm</th><th>状态</th><th>结论</th><th>说明</th></tr>
          </thead>
          <tbody>
            {#each logs as row}
              <tr>
                <td>{row.id}</td>
                <td>{row.chainage}</td>
                <td>{row.delta_mm}</td>
                <td><span class="tag {row.status === 'pending' ? 'pending' : 'ok'}">{row.status === 'pending' ? '待处理' : '已完成'}</span></td>
                <td>
                  {#if row.verdict}
                    <span class="tag {row.verdict === '合格' ? 'ok' : 'bad'}">{row.verdict}</span>
                  {:else}—{/if}
                </td>
                <td>{row.reason ?? "—"}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </section>
    {:else}
      <!-- 夜间提醒专页 -->
      <section>
        <div class="lamp-row">
          <div class="lamp {nightState?.light_on ? 'on' : ''}"></div>
          <div>
            <div class="lamp-text big {nightState?.light_on ? 'lamp-on' : 'lamp-off'}">
              {nightState?.light_on ? "提醒灯亮：夜间低办结，请值班关注" : "提醒灯灭"}
            </div>
            <div class="readonly-note">提醒仅用于通知值班，不会拒收任何交单；白天交单照常放行。</div>
          </div>
        </div>
        {#if nightState}
          <div class="metrics">
            <div class="metric"><div class="k">服务端时间</div><div class="v" style="font-size:0.95rem">{nightState.local_time}</div></div>
            <div class="metric"><div class="k">是否夜间时段</div><div class="v">{nightState.in_night_window ? "是" : "否"}</div></div>
            <div class="metric"><div class="k">近窗办结（条）</div><div class="v">{nightState.recent_done}</div></div>
            <div class="metric"><div class="k">低样本阈值</div><div class="v">{nightState.setting.low_sample_threshold}</div></div>
          </div>
        {/if}
      </section>

      <section>
        {#if isWriter}
          <label>夜间时段与低样本阈值（服务端本地时钟）</label>
          <div class="form-grid">
            <div>
              <label>夜间开始</label>
              <input type="time" bind:value={fStart} on:input={() => (formTouched = true)} />
            </div>
            <div>
              <label>夜间结束</label>
              <input type="time" bind:value={fEnd} on:input={() => (formTouched = true)} />
            </div>
            <div>
              <label>近窗分钟</label>
              <input type="number" min="1" max="1440" bind:value={fWindow} on:input={() => (formTouched = true)} />
            </div>
            <div>
              <label>低样本阈值</label>
              <input type="number" min="0" bind:value={fThreshold} on:input={() => (formTouched = true)} />
            </div>
          </div>
          <p class="hint">跨午夜时段直接填写，如 22:00–06:00。亮灯条件：当前落在夜间窗 且 近窗办结数 &lt; 阈值。</p>
          <button disabled={nightSaving} on:click={saveNight}>保存并重新判定</button>
          <button class="secondary" disabled={nightSaving} on:click={clearDone} style="margin-left:0.5rem">清空近窗办结（演练）</button>
          {#if nightError}<p class="err">{nightError}</p>{/if}
        {:else}
          <p class="readonly-note">巡检员只读：阈值与提醒履历如下，不可修改。</p>
          {#if nightState}
            <div class="metrics">
              <div class="metric"><div class="k">夜间时段</div><div class="v" style="font-size:0.95rem">{nightState.setting.night_start}–{nightState.setting.night_end}</div></div>
              <div class="metric"><div class="k">近窗分钟</div><div class="v">{nightState.setting.window_minutes}</div></div>
              <div class="metric"><div class="k">低样本阈值</div><div class="v">{nightState.setting.low_sample_threshold}</div></div>
            </div>
          {/if}
        {/if}
      </section>

      <section>
        <label>提醒流水（亮灯 / 灭灯履历）</label>
        <table>
          <thead>
            <tr><th>编号</th><th>灯</th><th>时间(服务端)</th><th>夜间窗</th><th>近窗办结</th><th>阈值</th><th>说明</th></tr>
          </thead>
          <tbody>
            {#each reminders as r}
              <tr>
                <td>{r.id}</td>
                <td>
                  <span class="tag {r.kind === 'on' ? 'bad' : 'ok'}">{r.kind === 'on' ? '亮灯' : '灭灯'}</span>
                </td>
                <td>{r.created_at}</td>
                <td>{r.in_night_window ? "是" : "否"}</td>
                <td>{r.recent_done}</td>
                <td>{r.low_sample_threshold}</td>
                <td>{r.reason}</td>
              </tr>
            {:else}
              <tr><td colspan="7" class="readonly-note">暂无提醒履历</td></tr>
            {/each}
          </tbody>
        </table>
      </section>
    {/if}
  {/if}
</main>
