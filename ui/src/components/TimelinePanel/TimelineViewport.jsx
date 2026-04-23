export default function TimelineViewport({ scrollerRef, rowsRef, onMouseDown, onScroll, onClick, onContextMenu }) {
  return (
    <div className="timeline-scroller" ref={scrollerRef} onMouseDown={onMouseDown} onScroll={onScroll}>
      <div className="timeline-rows empty" ref={rowsRef} onClick={onClick} onContextMenu={onContextMenu}>Load a song to inspect the synchronized timeline lanes.</div>
    </div>
  );
}