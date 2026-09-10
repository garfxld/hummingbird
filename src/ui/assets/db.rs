use std::{borrow::Cow, io::Cursor};

use anyhow::anyhow;
use image::{ImageFormat, imageops};
use sqlx::SqlitePool;
use url::Url;

fn crop_to_square(image_bytes: &[u8]) -> anyhow::Result<Vec<u8>> {
    let decoded = image::ImageReader::new(Cursor::new(image_bytes))
        .with_guessed_format()?
        .decode()?
        .into_rgb8();

    let (w, h) = decoded.dimensions();
    let side = w.min(h);
    let cropped = imageops::crop_imm(&decoded, (w - side) / 2, (h - side) / 2, side, side)
        .to_image();

    let mut buf = Vec::new();
    cropped.write_to(&mut Cursor::new(&mut buf), ImageFormat::Png)?;
    Ok(buf)
}

pub fn load(pool: &SqlitePool, url: Url) -> gpui::Result<Option<Cow<'static, [u8]>>> {
    let host = url
        .host_str()
        .ok_or_else(|| anyhow!("missing table name"))?;
    match host {
        "album" | "track" => {
            let mut segments = url.path_segments().ok_or_else(|| anyhow!("missing path"))?;
            let id: i64 = segments
                .next()
                .ok_or_else(|| anyhow!("missing id"))?
                .parse()?;
            let image_type = segments
                .next()
                .ok_or_else(|| anyhow!("missing image type"))?;

let query = match (host, image_type) {
                ("album", "thumb") => include_str!("../../../queries/assets/find_album_thumb.sql"),
                ("album", "full") | ("album", "square") => {
                    include_str!("../../../queries/assets/find_album_art.sql")
                }
                ("track", "thumb") => {
                    include_str!("../../../queries/assets/find_track_thumb.sql")
                }
                ("track", "full") => include_str!("../../../queries/assets/find_track_art.sql"),
                _ => unimplemented!("invalid image type '{image_type}'"),
            };

            let row: Option<(Option<Vec<u8>>,)> =
                crate::RUNTIME.block_on(sqlx::query_as(query).bind(id).fetch_optional(pool))?;

            let Some((Some(image),)) = row else {
                return Ok(None);
            };
            if image.is_empty() {
                return Ok(None);
            }

            let image = if image_type == "square" {
                crop_to_square(&image)?
            } else {
                image
            };

            Ok(Some(Cow::Owned(image)))
        }
        _ => Ok(None),
    }
}
