export default function PathsPanel() {
  return (
    <section className="panel controls">
      <h2>Available Paths</h2>
      <ul className="path-list">
        <li><code>/data/artifacts/&lt;Song - Artist&gt;/</code></li>
        <li><code>/data/output/&lt;Song - Artist&gt;/</code></li>
        <li><code>/data/songs/&lt;Song - Artist&gt;.mp3</code></li>
      </ul>
    </section>
  );
}