const CARD_WIDTH = 420;
const VIEWPORT_MARGIN = 16;
const VERTICAL_OFFSET = 14;

export function resolvePosition(anchorPosition) {
  if (!anchorPosition) {
    return { top: VIEWPORT_MARGIN, left: VIEWPORT_MARGIN };
  }
  const viewportWidth = window.innerWidth || CARD_WIDTH;
  const viewportHeight = window.innerHeight || 640;
  const availableWidth = Math.max(viewportWidth - (VIEWPORT_MARGIN * 2), 280);
  const cardWidth = Math.min(CARD_WIDTH, availableWidth);
  const prefersLeftSide = anchorPosition.x + cardWidth + VIEWPORT_MARGIN > viewportWidth;
  const left = prefersLeftSide ? Math.max(VIEWPORT_MARGIN, anchorPosition.x - cardWidth - VIEWPORT_MARGIN) : Math.min(anchorPosition.x + VIEWPORT_MARGIN, viewportWidth - cardWidth - VIEWPORT_MARGIN);
  const top = Math.min(Math.max(anchorPosition.y + VERTICAL_OFFSET, VIEWPORT_MARGIN), Math.max(VIEWPORT_MARGIN, viewportHeight - 320));
  return { top, left };
}