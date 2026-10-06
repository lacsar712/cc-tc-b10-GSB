<script>
  export let night; // 状态：{config, server_time, in_night_window, recent_count, light_on}
  export let events; // 提醒流水
  export let isWriter;
  export let headersFn;
  export let onSaved;

  let form = { night_start: "22:00", night_end: "06:00", threshold: 3, recent_hours: 2 };
  let synced = false;
  let saving = false;
  let err = "";
  let ok = "";

  $: if (night && !synced) {
    form = {
      night_start: night.config.night_start,
      night_end: night.config.night_end,
      threshold: night.config.threshold,
      recent_hours: night.config.recent_hours,
    };
    synced = true;
  }

  function fmtTime(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    return isNaN(d) ? iso : d.toLocaleString("zh-CN", { hour12: false });
  }

  async function save() {
    err = "";
    ok = "";
    saving = true;
    try {
      const res = await fetch("/api/night-reminder", {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...headersFn() },
        body: JSON.stringify({
          night_start: form.night_start,
          night_end: form.night_end,
          threshold: Number(form.threshold),
          recent_hours: Number(form.recent_hours),
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        err = data.detail || "保存失败";
        return;
      }
      ok = "已保存并按新设置重新判定";
      await onSaved();
    } catch {
      err = "保存时网络异常";
    } finally {
      saving = false;
    }
  }
</script>

<section class="lamp-sec">
  <div class="lamp-row">
    <span class="lamp {night && night.light_on ? 'lit' : ''}"></span>
    <div>
      <div class="lamp-text">
        {#if !night}
          正在读取夜间提醒状态…
        {:else if night.light_on}
          提醒灯亮：夜间时段内近窗办结偏低，请提醒值班核对
        {:else}
          提醒灯灭：未触发夜间低样本提醒
        {/if}
      </div>
      {#if night}
        <div class="lamp-sub">
          服务端时间 {fmtTime(night.server_time)} ·
          当前{night.in_night_window ? "在" : "不在"}夜间时段
          {night.config.night_start}-{night.config.night_end} ·
          近 {night.config.recent_hours} 小时办结 {night.recent_count} 起
          （阈值 {night.config.threshold}）
        </div>
      {/if}
    </div>
  </div>
  <p class="hint">提醒仅用于提示值班，不拦截任何交单：白天测缝照常放行；拱顶二衬龄期不足时这条提醒仍只是提醒。</p>
</section>

<section>
  <h2>提醒设置</h2>
  {#if night && isWriter}
    <div class="grid">
      <div>
        <label>夜间开始（HH:MM）</label>
        <input type="time" bind:value={form.night_start} />
      </div>
      <div>
        <label>夜间结束（HH:MM）</label>
        <input type="time" bind:value={form.night_end} />
      </div>
      <div>
        <label>低样本阈值（起）</label>
        <input type="number" min="1" max="999" step="1" bind:value={form.threshold} />
      </div>
      <div>
        <label>近窗时长（小时）</label>
        <input type="number" min="0.1" max="72" step="0.5" bind:value={form.recent_hours} />
      </div>
    </div>
    <button disabled={saving} on:click={save}>保存设置</button>
    {#if err}<p class="err">{err}</p>{/if}
    {#if ok}<p class="okmsg">{ok}</p>{/if}
  {:else if night}
    <dl class="ro">
      <div><dt>夜间时段</dt><dd>{night.config.night_start} - {night.config.night_end}</dd></div>
      <div><dt>低样本阈值</dt><dd>{night.config.threshold} 起</dd></div>
      <div><dt>近窗时长</dt><dd>{night.config.recent_hours} 小时</dd></div>
      <div><dt>最近修改</dt><dd>{night.config.updated_by ?? "—"} · {fmtTime(night.config.updated_at)}</dd></div>
    </dl>
    <p class="hint">巡检员只读阈值与提醒履历，修改请用测量员账号。</p>
  {:else}
    <p class="hint">加载中…</p>
  {/if}
</section>

<section>
  <h2>提醒流水</h2>
  <table>
    <thead>
      <tr><th>时间</th><th>夜间时段</th><th>近窗办结</th><th>阈值</th><th>说明</th></tr>
    </thead>
    <tbody>
      {#each events as ev}
        <tr>
          <td>{fmtTime(ev.triggered_at)}</td>
          <td>{ev.night_start}-{ev.night_end}</td>
          <td>{ev.recent_count} 起</td>
          <td>{ev.threshold}</td>
          <td>{ev.note}</td>
        </tr>
      {:else}
        <tr><td colspan="5" class="hint">暂无提醒记录</td></tr>
      {/each}
    </tbody>
  </table>
</section>

<style>
  h2 { font-size: 1rem; margin: 0 0 0.75rem; color: #fcd34d; }
  .lamp-sec { border-color: #57534e; }
  .lamp-row { display: flex; align-items: center; gap: 0.9rem; }
  .lamp {
    width: 34px; height: 34px; border-radius: 50%; flex: none;
    background: #44403c; border: 2px solid #57534e;
  }
  .lamp.lit {
    background: #f59e0b; border-color: #fbbf24;
    box-shadow: 0 0 14px 3px rgba(245, 158, 11, 0.55);
  }
  .lamp-text { font-weight: 600; }
  .lamp-sub { color: #a8a29e; font-size: 0.85rem; margin-top: 0.2rem; }
  .hint { color: #a8a29e; font-size: 0.85rem; margin-bottom: 0; }
  .grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 0 1rem; }
  .ro { display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.5rem 1rem; margin: 0 0 0.5rem; }
  .ro dt { color: #a8a29e; font-size: 0.8rem; }
  .ro dd { margin: 0.15rem 0 0; font-weight: 600; }
  .err { color: #fb7185; }
  .okmsg { color: #86efac; }
</style>
