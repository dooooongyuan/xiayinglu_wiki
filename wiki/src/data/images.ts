const optimizedIconPattern = /^\/game\/(equipment|materials|danyao|wuxue|zhuwen|traps)\/(.+)\.png$/i;

export function optimizedGameImage(source: string): string {
  const match = source.match(optimizedIconPattern);
  return match ? `/game/optimized/${match[1]}/${match[2]}.webp` : source;
}

export function characterPortraitThumbnail(source: string): string {
  return source
    ? source.replace('/game/characters/', '/game/characters/thumbs/').replace(/\.png$/i, '.webp')
    : '';
}

export function characterPortraitDetail(source: string): string {
  return source
    ? source.replace('/game/characters/', '/game/characters/detail/').replace(/\.png$/i, '.webp')
    : '';
}
