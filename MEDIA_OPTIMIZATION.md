# Gallery video optimization

All six project-gallery videos were re-encoded as H.264 MP4 for broad browser compatibility. The existing filenames and paths are unchanged, so the templates and JavaScript do not need to be updated.

- Portrait dimensions preserved: 478 × 850
- Frame rate preserved: 30 fps
- Video target: 400 kbps, capped at 480 kbps
- Audio stream copied without re-encoding
- MP4 fast-start metadata enabled for progressive playback

## Size comparison

| File | Before | After | Reduction |
|---|---:|---:|---:|
| `work-video-01.mp4` | 20.88 MB | 13.48 MB | 35.5% |
| `work-video-02.mp4` | 6.59 MB | 4.24 MB | 35.6% |
| `work-video-03.mp4` | 5.03 MB | 3.20 MB | 36.4% |
| `work-video-04.mp4` | 6.34 MB | 4.51 MB | 28.8% |
| `work-video-05.mp4` | 6.84 MB | 4.46 MB | 34.7% |
| `work-video-06.mp4` | 7.32 MB | 4.74 MB | 35.2% |

**Combined video size:** 52.99 MB → 34.64 MB (18.36 MB saved; 34.6% reduction).

## GitHub browser upload note

GitHub browser uploads limit each individual file to 25 MiB. The complete ZIP is still larger than that because it contains the whole project; extract the archive before uploading source files. The largest optimized video is now below 14 MB. If uploading many files at once fails, upload the `static` contents in smaller batches while preserving the folder structure. See the official docs: https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository.
