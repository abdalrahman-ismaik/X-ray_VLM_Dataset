#If you remove crops from the pidray_class_crops folders, this script will help you identify 
#which JSON bboxes are affected and allow you to remove them from the JSON annotations. It checks each bbox in the 
# JSON files against the expected crop files and prompts you to confirm deletion of any orphaned bboxes.

"""
Missing Crops Detector: Identify missing crop files and remove orphaned bboxes from JSONs.

This script iterates through all JSON annotation files and checks if the corresponding
crop files exist in the pidray_class_crops folders. For each missing crop, it prompts
the user to confirm deletion of that bbox from the JSON.

Workflow:
1. Load each JSON file from the dataset
2. For each bbox/shape with a label:y
   - Convert label (spaces → underscores) to get the expected folder name
   - Construct expected crop filename: imageStem__FolderName__Index.jpg
   - Check if crop exists in pidray_class_crops/{FolderName}/
3. If crop is missing:
   - Prompt user: "Crop 'xray_00020__Laptop_Power_Adapter__003.jpg' is missing. Delete this bbox from '{json}' (y/n)?"
   - If 'y': Remove bbox from JSON shapes list
   - If 'n': Keep bbox, continue
4. Save modified JSONs
5. Report statistics
"""

import os
import json
from pathlib import Path
from tqdm import tqdm

# Configuration
CROP_ROOT = r"C:\Users\4bais\X-ray_VLM_Dataset\batch_1\class_crops"
JSON_DIR = r"C:\Users\4bais\X-ray_VLM_Dataset\batch_1\json"
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


def label_to_folder_name(label: str) -> str:
    """
    Convert a label to the corresponding folder name.
    
    Examples:
    - "Laptop Power Adapter" → "Laptop_Power_Adapter"
    - "Mobile_Phone" → "Mobile_Phone"
    - "Cable" → "Cable"
    
    Spaces are converted to underscores to match folder naming convention.
    """
    base_label = get_base_label(label)
    return base_label.replace(" ", "_")


def construct_crop_filename(image_stem: str, label: str, bbox_index: int) -> str:
    """
    Construct the expected crop filename for a given bbox.
    
    Args:
        image_stem: The image filename without extension (e.g., "xray_00020")
        label: The bbox label (e.g., "Laptop Power Adapter")
        bbox_index: The bbox index (1-indexed)
    
    Returns:
        str: The expected crop filename (e.g., "xray_00020__Laptop_Power_Adapter__003.jpg")
    """
    folder_name = label_to_folder_name(label)
    return f"{image_stem}__{folder_name}__{bbox_index:03d}.jpg"


def load_json(path):
    """Load JSON file."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(obj, path):
    """Save JSON file."""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def crop_exists(label: str, crop_filename: str) -> bool:
    """
    Check if a crop file exists in the pidray_class_crops folder.
    
    Args:
        label: The bbox label (e.g., "Laptop Power Adapter")
        crop_filename: The expected crop filename
    
    Returns:
        bool: True if crop exists, False otherwise
    """
    folder_name = label_to_folder_name(label)
    crop_path = os.path.join(CROP_ROOT, folder_name, crop_filename)
    return os.path.isfile(crop_path)


def prompt_delete_bbox(json_name: str, crop_filename: str) -> bool:
    """
    Prompt user to confirm deletion of a bbox.
    
    Args:
        json_name: The JSON filename
        crop_filename: The missing crop filename
    
    Returns:
        bool: True if user confirmed deletion ('y'), False otherwise
    """
    response = input(
        f"\nCrop '{crop_filename}' is missing.\n"
        f"Delete this bbox from '{json_name}'? (y/n): "
    ).strip().lower()
    return response == 'y'


def process_jsons():
    """
    Process all JSON files, check for missing crops, and prompt user for deletions.
    
    Returns:
        dict: statistics about the operation
    """
    if not os.path.isdir(CROP_ROOT):
        print(f"ERROR: CROP_ROOT not found: {CROP_ROOT}")
        return {}
    
    if not os.path.isdir(JSON_DIR):
        print(f"ERROR: JSON_DIR not found: {JSON_DIR}")
        return {}
    
    stats = {
        "jsons_processed": 0,
        "jsons_updated": 0,
        "bboxes_checked": 0,
        "bboxes_deleted": 0,
        "crops_missing": 0,
        "errors": []
    }
    
    # Get all JSON files
    json_files = [f for f in os.listdir(JSON_DIR) if f.endswith('.json')]
    json_files.sort()
    
    print(f"Found {len(json_files)} JSON files to process\n")
    
    pbar = tqdm(total=len(json_files), desc="Processing JSONs", unit="file")
    
    for json_filename in json_files:
        json_path = os.path.join(JSON_DIR, json_filename)
        image_stem = Path(json_filename).stem
        
        try:
            data = load_json(json_path)
        except Exception as e:
            stats["errors"].append(f"Failed to load {json_filename}: {e}")
            pbar.update(1)
            continue
        
        stats["jsons_processed"] += 1
        shapes = data.get("shapes", [])
        
        if not isinstance(shapes, list):
            stats["errors"].append(f"Invalid shapes in {json_filename}")
            pbar.update(1)
            continue
        
        # Check each bbox
        shapes_to_delete = []  # Collect indices of shapes to delete
        
        for bbox_idx, shape in enumerate(shapes):
            stats["bboxes_checked"] += 1
            
            if shape.get("shape_type") != "rectangle":
                continue
            
            label = shape.get("label", "")
            if not label:
                continue
            
            # Construct expected crop filename (bbox_idx is 0-indexed, but crop uses 1-indexed)
            crop_filename = construct_crop_filename(image_stem, label, bbox_idx + 1)
            
            # Check if crop exists
            if not crop_exists(label, crop_filename):
                stats["crops_missing"] += 1
                
                # Pause progress bar before prompting user
                pbar.close()
                
                # Prompt user (not in background mode)
                if prompt_delete_bbox(json_filename, crop_filename):
                    shapes_to_delete.append(bbox_idx)
                
                # Resume progress bar
                pbar = tqdm(total=len(json_files), desc="Processing JSONs", unit="file", 
                           initial=stats["jsons_processed"])
        
        # Delete shapes in reverse order to maintain correct indices
        if shapes_to_delete:
            for idx in sorted(shapes_to_delete, reverse=True):
                del shapes[idx]
                stats["bboxes_deleted"] += 1
            
            # Save modified JSON
            try:
                save_json(data, json_path)
                stats["jsons_updated"] += 1
                pbar.write(f"✓ Saved {json_filename} with {len(shapes_to_delete)} bbox(es) deleted")
            except Exception as e:
                stats["errors"].append(f"Failed to save {json_filename}: {e}")
        
        pbar.update(1)
    
    pbar.close()
    return stats


def main():
    print("=" * 70)
    print("MISSING CROPS DETECTOR - Validate Crops and Remove Orphaned BBoxes")
    print("=" * 70)
    print(f"Crop Root: {CROP_ROOT}")
    print(f"JSON Dir:  {JSON_DIR}")
    print()
    
    stats = process_jsons()
    
    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    
    print(f"JSONs processed:       {stats['jsons_processed']}")
    print(f"JSONs updated:         {stats['jsons_updated']}")
    print(f"BBoxes checked:        {stats['bboxes_checked']}")
    print(f"Crops missing:         {stats['crops_missing']}")
    print(f"BBoxes deleted:        {stats['bboxes_deleted']}")
    
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
