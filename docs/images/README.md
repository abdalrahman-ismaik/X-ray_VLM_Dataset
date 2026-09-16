# GUI screenshots

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
