// Draw the validated current result at the decoded image's original dimensions.
// This module encodes a PNG; the caller decides whether its snapshot is still current.
export async function createAnnotatedPng(image, predictions) {
  const decoded = new Image();
  decoded.src = image.image;
  await decoded.decode();
  const canvas = document.createElement('canvas');
  canvas.width = image.width;
  canvas.height = image.height;
  const context = canvas.getContext('2d');
  if (!context) throw new Error('A drawing surface could not be created.');
  try {
    context.drawImage(decoded, 0, 0, image.width, image.height);
    const shortSide = Math.min(image.width, image.height);
    const fontSize = Math.max(12, Math.min(40, Math.round(shortSide / 28)));
    const padding = Math.max(3, Math.round(fontSize / 4));
    context.font = `600 ${fontSize}px "Segoe UI", sans-serif`;
    context.textBaseline = 'middle';
    context.lineWidth = Math.max(2, Math.min(8, Math.round(shortSide / 220)));
    context.lineJoin = 'round';
    for (const { label, score, box, color } of predictions) {
      const x = box.xmin * image.width;
      const y = box.ymin * image.height;
      const width = (box.xmax - box.xmin) * image.width;
      const height = (box.ymax - box.ymin) * image.height;
      context.strokeStyle = color;
      context.strokeRect(x, y, width, height);

      const text = `${label} ${score.toFixed(2)}`;
      const tagWidth = Math.min(image.width, Math.ceil(context.measureText(text).width) + padding * 2);
      const tagHeight = Math.min(image.height, fontSize + padding * 2);
      const tagX = Math.max(0, Math.min(x, image.width - tagWidth));
      const preferredY = y >= tagHeight ? y - tagHeight : y;
      const tagY = Math.max(0, Math.min(preferredY, image.height - tagHeight));
      context.fillStyle = color;
      context.fillRect(tagX, tagY, tagWidth, tagHeight);
      context.fillStyle = '#ffffff';
      // maxWidth keeps even a long class label inside a narrow source image.
      const textPadding = Math.min(padding, tagWidth / 4);
      context.fillText(text, tagX + textPadding, tagY + tagHeight / 2,
        Math.max(0.1, tagWidth - textPadding * 2));
    }
    return await new Promise((resolve, reject) => {
      const deadline = setTimeout(() => reject(new DOMException('PNG encoding timed out.', 'TimeoutError')), 15_000);
      try {
        canvas.toBlob((blob) => {
          clearTimeout(deadline);
          if (blob) resolve(blob);
          else reject(new Error('PNG encoding returned no image.'));
        }, 'image/png');
      } catch (error) {
        clearTimeout(deadline);
        reject(error);
      }
    });
  } finally {
    // Release the extra pixel buffer after encoding, including failed encodes.
    canvas.width = 0;
    canvas.height = 0;
  }
}

export function resultFilename(filename, minimum) {
  const stem = filename.replace(/\.[^.]*$/, '').replace(/[<>:"/\\|?*\u0000-\u001f]/g, '-')
    .trim().slice(0, 100) || 'image';
  return `${stem}-object-lens-min-${minimum.toFixed(2)}.png`;
}
