# README visuals

## Animated walkthrough

The [GIF](gui-demo.gif) and [MP4](gui-demo.mp4) show a real session of the
Tkinter application at commit `81a986d`, recorded on Windows on 2026-09-16.
The silent, looping GIF is 960 × 540 at 10 fps (about 6.1 MB); the sharper
1440 × 810 MP4 is 20 fps (about 5.5 MB). Both run for 40 seconds.

The walkthrough starts in Image Browser with the Box class and scrolls down
through its crops. It applies Unapproved, the app's pending-review filter,
selects and approves two batches of three crops, then switches to Approved to
show those six crops in the same class. Approval is saved immediately to the
temporary partition's review state; it does not change annotation labels.

The recording then returns to Unapproved, opens a linked image and crop,
zooms in, resizes a bounding box, reviews the pending annotation edit, and saves it.
The application then refreshes the affected crops and clears the pending queue.
Capture pauses during the save worker, so that waiting time is omitted. Six
brief blank redraw frames are held on adjacent, unaltered application captures.

This session used a disposable copy of 20 paired X-ray images and annotation
files, containing 46 Box crops. The approvals and sample resize were saved only
in that copy. Hash checks confirmed that the original sample images and
annotations were unchanged. The demonstration
illustrates the controls, not a validated labeling decision.

Frames were captured directly from the application window. HyperFrames added
the numbered captions and terminal-style text reveals above the recording;
FFmpeg encoded the MP4 and optimized the GIF. No app controls or results were
fabricated. Temporary recordings, composition files, and tooling stay outside
the repository.

The [terminal header](readme-header.svg) is a lightweight static vector banner.
Its typography, command prompt, and workflow text remain sharp when scaled.

## Still screenshots

These PNG files are actual captures of the Tkinter application at commit
`80b2d48`, taken on Windows on 2026-09-16. They are captured directly from the
application window, without desktop chrome, mockups, or image retouching.

| File | Application state |
| --- | --- |
| [image-browser.png](image-browser.png) | Generated crops, thumbnail zoom at 135%, active and unapproved filters. |
| [annotation-editor.png](annotation-editor.png) | Source image with three boxes, selected Box annotation, and linked crop preview. |
| [class-management.png](class-management.png) | The Classes tab with the built-in label catalog. |
| [pending-changes.png](pending-changes.png) | One staged Box-to-Power Bank relabel, shown only to demonstrate the pending queue. |

The capture session used copies of eight existing X-ray images and their
annotation JSON files in a temporary `demo-dataset` folder. It generated crops
only for that small sample. The demonstrated relabel was never saved. Original
research images and annotations were not changed, and the demo dataset is not
included in the repository. These images illustrate the interface, not validated
labeling decisions.

To refresh the screenshots:

1. Install the application and copy a small, suitable sample of paired images
   and JSON annotations to a disposable dataset folder.
2. Index that copy, generate crops for its selected partition, and use Resume.
3. Capture Image Browser, then open a crop in Image Viewer and capture the
   editor, Classes, and Pending tabs. Stage a sample edit only in the copy.
4. Capture the application window directly; exclude desktop content and local
   account paths. Keep the controls legible and use the existing filenames.
5. Verify the images visually and check their links in the [README](../../README.md).

Keep raw dataset files, generated crops, manifests, and temporary capture scripts
outside this documentation folder.
