"""
I use this when I move the proposal crops from one class folder to another (e.g., from "Bottle" to "Laptop") and I want to update the JSON annotations accordingly.



Reverse utility: Update JSON annotations based on current crop folder organization.

This script traverses the crop folders (pidray_class_crops) and updates the corresponding
JSON annotation files ONLY for crops that have been moved to a different folder.



Workflow:
1. Scans all subfolders in pidray_class_crops (each folder represents a class)
2. For each crop image found, parses its filename to extract: image_stem, original_class, index
3. Checks if the original_class (from filename) matches the folder name:
   - If MATCH: File is in correct folder → skip (no change)
   - If NO MATCH: File has been moved → update the JSON
4. For moved files: Updates the corresponding JSON's bbox at that index with the new class label
5. Coordinates remain unchanged
"""

import os
import json

from pathlib import Path
from collections import defaultdict
from tqdm import tqdm

# Configuration
CROP_ROOT = r"D:\GROMA\Abdelfatah_Annotations\Data from Abdelfatah after April2026\pidray_class_crops"
JSON_DIR = r"D:\GROMA\Abdelfatah_Annotations\Data from Abdelfatah after April2026\train\train\json"
STRIP_CONF_ALWAYS = True


def strip_conf(label: str) -> str:
    """Strip confidence values from labels."""
    s = (label or "").strip()
    if "__" in s:
        s = s.split("__")[0].strip()
    return s


def get_base_label(label: str) -> str:
    """Get base label, optionally stripping confidence."""
    return strip_conf(label) if STRIP_CONF_ALWAYS else (label or "").strip()


def parse_crop_filename(crop_filename):
    """
    Parse crop filename to extract image_stem, old_class, and index.
    
    Filename format: imageStem__OldClass__001.jpg
    
    Returns:
        tuple: (image_stem, old_class, index) or (None, None, None) if parse fails
    """
    stem = Path(crop_filename).stem  # Remove .jpg extension
    parts = stem.split("__")
    
    if len(parts) < 3:
        return None, None, None
    
    # Last part is the index
    try:
        index = int(parts[-1])
    except ValueError:
        return None, None, None
    
    # Second to last is the old class
    old_class = parts[-2]
    
    # Everything before that is the image stem
    image_stem = "__".join(parts[:-2])
    
    return image_stem, old_class, index


def load_json(path):
    """Load JSON file."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(obj, path):
    """Save JSON file."""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def update_jsons_from_crops():
    """
    Traverse crop folders and update JSON files ONLY for crops that have been moved.
    
    Logic:
    - For each crop file, extract the original class from filename (e.g., "Bottle")
    - Compare with the folder it's currently in (e.g., "Laptop")
    - If they don't match, the file was moved → update the JSON
    - If they match, the file is in the correct folder → skip (no change needed)
    
    Returns:
        dict: statistics about the update operation
    """
    if not os.path.isdir(CROP_ROOT):
        print(f"ERROR: CROP_ROOT not found: {CROP_ROOT}")
        return {}
    
    if not os.path.isdir(JSON_DIR):
        print(f"ERROR: JSON_DIR not found: {JSON_DIR}")
        return {}
    
    stats = {
        "total_crops": 0,
        "jsons_updated": 0,
        "bboxes_updated": 0,
        "crops_skipped": 0,
        "errors": [],
        "updates": []  # Track each update: (filename, old_class, new_class)
    }
    
    # Collect all crops and their target classes
    crops_by_json = defaultdict(list)  # json_filename -> [(image_stem, target_class, index), ...]
    
    print(f"Scanning crop folders in {CROP_ROOT}...\n")
    
    # Iterate through all class folders
    for class_folder in os.listdir(CROP_ROOT):
        class_path = os.path.join(CROP_ROOT, class_folder)
        
        if not os.path.isdir(class_path):
            continue
        
        target_class = class_folder  # The folder name is the target class
        
        # Iterate through all crop images in this class folder
        for crop_filename in os.listdir(class_path):
            crop_path = os.path.join(class_path, crop_filename)
            
            if not os.path.isfile(crop_path):
                continue
            
            if not crop_filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue
            
            # Parse crop filename
            image_stem, old_class, index = parse_crop_filename(crop_filename)
            
            if image_stem is None:
                error_msg = f"Failed to parse crop: {crop_filename}"
                stats["errors"].append(error_msg)
                continue
            
            # Find corresponding JSON file
            json_filename = f"{image_stem}.json"
            
            # Track this crop
            crops_by_json[json_filename].append({
                "target_class": target_class,
                "index": index,
                "crop_filename": crop_filename,
                "old_class": old_class
            })
            stats["total_crops"] += 1
    
    print(f"Found {stats['total_crops']} crops across all class folders")
    print(f"Will process {len(crops_by_json)} JSON files\n")
    
    # Now process each JSON file
    for json_filename, crops_list in tqdm(crops_by_json.items(), desc="Updating JSON files", unit="file"):
        json_path = os.path.join(JSON_DIR, json_filename)
        
        if not os.path.exists(json_path):
            stats["errors"].append(f"JSON not found: {json_filename}")
            continue
        
        try:
            data = load_json(json_path)
        except Exception as e:
            stats["errors"].append(f"Failed to load {json_filename}: {e}")
            continue
        
        shapes = data.get("shapes", [])
        if not isinstance(shapes, list):
            stats["errors"].append(f"Invalid shapes in {json_filename}")
            continue
        
        file_modified = False
        
        # Update each bbox based on crops
        for crop_info in crops_list:
            target_class = crop_info["target_class"]
            old_class = crop_info["old_class"]
            index = crop_info["index"]
            crop_filename = crop_info["crop_filename"]
            
            # Only update if the file was moved to a different folder
            # (i.e., old_class != target_class)
            if old_class == target_class:
                # File is in the correct folder, no update needed
                stats["crops_skipped"] += 1
                continue
            
            # Index in filename is 1-indexed, but shapes list is 0-indexed
            shape_idx = index - 1
            
            if not (0 <= shape_idx < len(shapes)):
                stats["errors"].append(
                    f"Shape index out of range in {json_filename}: "
                    f"index={index} (0-indexed: {shape_idx}), total shapes={len(shapes)}"
                )
                continue
            
            shape = shapes[shape_idx]
            
            if shape.get("shape_type") != "rectangle":
                stats["errors"].append(
                    f"Shape at index {shape_idx} in {json_filename} is not a rectangle"
                )
                continue
            
            # Update the label
            old_label = shape.get("label", "")
            new_label = target_class
            
            if old_label != new_label:
                shape["label"] = new_label
                file_modified = True
                stats["bboxes_updated"] += 1
                # Track this update
                stats["updates"].append({
                    "crop_filename": crop_filename,
                    "old_class": old_class,
                    "new_class": target_class
                })
        
        # Save if modified
        if file_modified:
            try:
                save_json(data, json_path)
                stats["jsons_updated"] += 1
            except Exception as e:
                stats["errors"].append(f"Failed to save {json_filename}: {e}")
    
    return stats


def main():
    print("=" * 70)
    print("REVERSE CROP UTILITY - Update JSONs from Crop Organization")
    print("=" * 70)
    print(f"Crop Root: {CROP_ROOT}")
    print(f"JSON Dir:  {JSON_DIR}")
    print()
    
    stats = update_jsons_from_crops()
    
    print()
    print("=" * 70)
    print("UPDATE RESULTS")
    print("=" * 70)
    
    print(f"Total crops scanned:      {stats['total_crops']}")
    print(f"Crops in correct folder:  {stats['crops_skipped']} (skipped - no change)")
    print(f"Crops moved to new folder: {stats['total_crops'] - stats['crops_skipped']} (updated)")
    print(f"JSON files updated:       {stats['jsons_updated']}")
    print(f"BBoxes label changed:     {stats['bboxes_updated']}")
    
    if stats['updates']:
        print()
        print("-" * 80)
        print("DETAILED UPDATES:")
        print("-" * 80)
        print(f"{'Crop Filename':<45} {'Old Class':<18} → {'New Class':<18}")
        print("-" * 80)
        
        for update in sorted(stats['updates'], key=lambda x: x['crop_filename']):
            filename = update['crop_filename']
            old_cls = update['old_class']
            new_cls = update['new_class']
            print(f"{filename:<45} {old_cls:<18} → {new_cls:<18}")
        
        print("-" * 80)
    
    if stats['errors']:
        print()
        print(f"Errors ({len(stats['errors'])}):")
        for error in stats['errors'][:10]:
            print(f"  • {error}")
        if len(stats['errors']) > 10:
            print(f"  ... and {len(stats['errors']) - 10} more errors")
    
    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
    input("\nPress Enter to exit...")
