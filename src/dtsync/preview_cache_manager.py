"""
Darktable XMP Sync Tool
Copyright (C) 2025 Daniele Pighin

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.
"""

import os
import shutil
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QThreadPool, QMutex, QMutexLocker


class PreviewCacheManager(QObject):
    """Manages background preview generation for all files in the diff set."""
    
    # Signals
    cache_progress_updated = Signal(int, int)  # current, total
    cache_generation_finished = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.thread_pool = QThreadPool()
        self.mutex = QMutex()
        
        # Preview generation state
        self.diff_files = {}
        self.darktable_cli_path = ""
        self.preview_max_dimension = 800
        self.max_threads = 4
        self.enable_opencl = True
        
        # Job tracking
        self.pending_jobs = []
        self.active_jobs = {}
        self.completed_jobs = 0
        self.total_jobs = 0
        
        # Initialize preview signals to None, will be set up when needed
        self.preview_signals = None
        
    def _initialize_signals(self):
        """Initialize preview signals."""
        # Import preview classes at runtime
        try:
            from preview import PreviewSignals
            self.preview_signals = PreviewSignals(self)
            self.preview_signals.preview_ready.connect(self.on_preview_ready)
            self.preview_signals.preview_failed.connect(self.on_preview_failed)
            self.preview_signals.preview_retry_requested.connect(self.on_preview_retry_requested)
            self.preview_signals.job_finished.connect(self.on_job_finished)
        except ImportError:
            print("Warning: Could not import preview classes")
            self.preview_signals = None
        
    def update_settings(self, darktable_cli_path, preview_max_dimension, max_threads, enable_opencl=True):
        """Update preview generation settings."""
        settings_changed = (
            self.darktable_cli_path != darktable_cli_path or
            self.preview_max_dimension != preview_max_dimension or
            self.max_threads != max_threads or
            self.enable_opencl != enable_opencl
        )
        
        self.darktable_cli_path = darktable_cli_path
        self.preview_max_dimension = preview_max_dimension
        self.max_threads = max_threads
        self.enable_opencl = enable_opencl
        
        # Update thread pool max count
        self.thread_pool.setMaxThreadCount(max_threads)
        
        # If preview dimension changed, clear cache for old size and regenerate
        if settings_changed and self.preview_max_dimension != preview_max_dimension:
            self.clear_cache_for_dimension(self.preview_max_dimension)
            
    def clear_cache_for_dimension(self, dimension):
        """Clear cache for a specific dimension."""
        cache_dir = os.path.join(Path.home(), ".cache", "dtsync", str(dimension))
        if os.path.exists(cache_dir):
            try:
                shutil.rmtree(cache_dir)
                print(f"Cleared preview cache for dimension {dimension}")
            except OSError as e:
                print(f"Error clearing cache for dimension {dimension}: {e}")
                
    def clear_all_caches(self):
        """Clear all preview caches."""
        cache_dir = os.path.join(Path.home(), ".cache", "dtsync")
        if os.path.exists(cache_dir):
            try:
                shutil.rmtree(cache_dir)
                print("Cleared all preview caches")
            except OSError as e:
                print(f"Error clearing all caches: {e}")
    
    def clear_cache_for_file(self, relative_path, session_path, archive_path):
        """Clear cache for a specific file's previews."""
        cache_dir = os.path.join(Path.home(), ".cache", "dtsync", str(self.preview_max_dimension))
        if not os.path.exists(cache_dir):
            return
        
        print(f"Clearing cache for {relative_path}")
        
        # Find the file_info to get the hash values
        file_info = self.diff_files.get(relative_path) if self.diff_files else None
        if not file_info:
            print(f"No file info found for {relative_path}")
            return
        
        # Get the hash values used for caching
        work_hash = file_info.get("session_data", {}).get("top_level_attrs", {}).get("history_current_hash")
        ref_hash = file_info.get("archive_data", {}).get("top_level_attrs", {}).get("history_current_hash")
        
        # Also calculate fallback hashes (in case history_current_hash is not available)
        session_fallback_hash = str(hash(session_path)) if session_path else None
        archive_fallback_hash = str(hash(archive_path)) if archive_path else None
        
        # Collect all possible hash values
        possible_hashes = []
        if work_hash:
            possible_hashes.append(work_hash)
        if ref_hash:
            possible_hashes.append(ref_hash)
        if session_fallback_hash:
            possible_hashes.append(session_fallback_hash)
        if archive_fallback_hash:
            possible_hashes.append(archive_fallback_hash)
        
        print(f"Looking for cache files with hashes: {possible_hashes}")
        
        # Remove cached files
        removed_count = 0
        try:
            for filename in os.listdir(cache_dir):
                if filename.endswith('.jpg'):
                    # Get hash parts - the filename format is {hash}_{image_type}.jpg
                    parts = filename.split('_')
                    if len(parts) >= 2:
                        hash_part = parts[0]
                        
                        if hash_part in possible_hashes:
                            cache_file_path = os.path.join(cache_dir, filename)
                            try:
                                os.remove(cache_file_path)
                                print(f"Removed cached preview: {filename}")
                                removed_count += 1
                            except OSError as e:
                                print(f"Error removing cache file {filename}: {e}")
            
            if removed_count == 0:
                print(f"No cache files found to remove for {relative_path}")
            else:
                print(f"Removed {removed_count} cache files for {relative_path}")
                
        except OSError as e:
            print(f"Error clearing cache for file {relative_path}: {e}")
                
    def set_diff_files(self, diff_files):
        """Set the diff files and schedule preview generation."""
        self.cancel_all_jobs()
        self.diff_files = diff_files
        self.schedule_preview_generation()
        
    def request_preview_generation(self, relative_path, raw_file, session_path, archive_path, work_hash, ref_hash):
        """Request immediate preview generation for a specific file (called by UI)."""
        if not self.darktable_cli_path:
            return
            
        # Check if already cached and emit signal if so
        for image_type, xmp_path, hash_val in [("session", session_path, work_hash), ("archive", archive_path, ref_hash)]:
            if self._is_preview_cached(relative_path, image_type, hash_val, xmp_path):
                output_path = self._get_cache_path(relative_path, image_type, hash_val, xmp_path)
                if self.preview_signals:
                    self.preview_signals.preview_ready.emit(relative_path, image_type, output_path)
                continue
                
            # Check if already scheduled
            if self.is_job_scheduled(relative_path, image_type):
                continue
                
            # Add to priority queue (front of the queue for immediate processing)
            job = {
                "relative_path": relative_path,
                "raw_file": raw_file,
                "xmp_file": xmp_path,
                "image_type": image_type,
                "history_hash": hash_val,
            }
            
            with QMutexLocker(self.mutex):
                # Insert at the beginning for priority
                self.pending_jobs.insert(0, job)
                
        # Start processing if not already running
        self.process_pending_jobs()
        
    def request_single_preview_generation(self, relative_path, raw_file, xmp_path, image_type, history_hash):
        """Request immediate preview generation for a single image (session or archive)."""
        if not self.darktable_cli_path:
            return
            
        # Check if already cached and emit signal if so
        if self._is_preview_cached(relative_path, image_type, history_hash, xmp_path):
            output_path = self._get_cache_path(relative_path, image_type, history_hash, xmp_path)
            if self.preview_signals:
                self.preview_signals.preview_ready.emit(relative_path, image_type, output_path)
            return
                
        # Check if already scheduled
        if self.is_job_scheduled(relative_path, image_type):
            return
            
        # Add to priority queue (front of the queue for immediate processing)
        job = {
            "relative_path": relative_path,
            "raw_file": raw_file,
            "xmp_file": xmp_path,
            "image_type": image_type,
            "history_hash": history_hash,
        }
        
        with QMutexLocker(self.mutex):
            # Insert at the beginning for priority
            self.pending_jobs.insert(0, job)
            
        # Start processing if not already running
        self.process_pending_jobs()
        
    def _is_preview_cached(self, relative_path, image_type, history_hash, xmp_file):
        """Check if a preview is already cached."""
        job = {
            "relative_path": relative_path,
            "image_type": image_type,
            "history_hash": history_hash,
            "xmp_file": xmp_file
        }
        return self._preview_exists(job)
        
    def _get_cache_path(self, relative_path, image_type, history_hash, xmp_file):
        """Get the cache path for a preview."""
        output_dir = os.path.join(Path.home(), ".cache", "dtsync", str(self.preview_max_dimension))
        hash_part = (
            f"{history_hash}"
            if history_hash
            else str(hash(xmp_file))
        )
        output_filename = f"{hash_part}_{image_type}.jpg"
        return os.path.join(output_dir, output_filename)
        
    def schedule_preview_generation(self):
        """Schedule preview generation for all files in the diff set."""
        if not self.darktable_cli_path or not self.diff_files:
            return
            
        # Import preview classes at runtime
        try:
            from preview import PreviewWorker
        except ImportError:
            print("Warning: Could not import preview classes")
            return
            
        # Ensure signals are initialized
        if self.preview_signals is None:
            self._initialize_signals()
            
        with QMutexLocker(self.mutex):
            self.pending_jobs.clear()
            self.active_jobs.clear()
            self.completed_jobs = 0
            
            # Generate preview jobs for all files
            for relative_path, file_info in self.diff_files.items():
                raw_file = self._find_raw_file(file_info["session_path"])
                if not raw_file:
                    continue
                    
                # Get history hashes
                work_hash = (
                    file_info["session_data"]
                    .get("top_level_attrs", {})
                    .get("history_current_hash")
                )
                ref_hash = (
                    file_info["archive_data"]
                    .get("top_level_attrs", {})
                    .get("history_current_hash")
                )
                
                # Create jobs for both session and archive versions
                jobs = [
                    {
                        "relative_path": relative_path,
                        "raw_file": raw_file,
                        "xmp_file": file_info["session_path"],
                        "image_type": "session",
                        "history_hash": work_hash,
                    },
                    {
                        "relative_path": relative_path,
                        "raw_file": raw_file,
                        "xmp_file": file_info["archive_path"],
                        "image_type": "archive",
                        "history_hash": ref_hash,
                    }
                ]
                
                # Filter out jobs where preview already exists
                for job in jobs:
                    if not self._preview_exists(job):
                        self.pending_jobs.append(job)
                        
            self.total_jobs = len(self.pending_jobs)
            
        # Start processing jobs
        print(f"Scheduled {self.total_jobs} preview generation jobs")
        self.process_pending_jobs()
        
    def _find_raw_file(self, xmp_path):
        """Find the corresponding raw file for an XMP file."""
        if xmp_path.lower().endswith(".xmp"):
            raw_file_base = xmp_path[:-4]
        else:
            raw_file_base = os.path.splitext(xmp_path)[0]
            
        possible_exts = [".nef", ".cr2", ".cr3", ".arw", ".dng", ".raf", ".orf", ".rw2"]
        
        # Handle cases like 'photo.cr2.xmp' -> 'photo.cr2'
        if any(raw_file_base.lower().endswith(x) for x in possible_exts) and os.path.exists(raw_file_base):
            return raw_file_base
            
        # Handle 'photo.xmp' -> 'photo' and find 'photo.cr2' etc.
        for ext in possible_exts:
            test_path_upper = raw_file_base + ext.upper()
            test_path_lower = raw_file_base + ext.lower()
            if os.path.exists(test_path_upper):
                return test_path_upper
            if os.path.exists(test_path_lower):
                return test_path_lower
                
        return None
        
    def _preview_exists(self, job):
        """Check if a preview already exists for the given job."""
        output_dir = os.path.join(Path.home(), ".cache", "dtsync", str(self.preview_max_dimension))
        hash_part = (
            f"{job['history_hash']}"
            if job['history_hash']
            else str(hash(job['xmp_file']))
        )
        output_filename = f"{hash_part}_{job['image_type']}.jpg"
        output_path = os.path.join(output_dir, output_filename)
        
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        
    def is_job_scheduled(self, rel_path, image_type):
        """Check if a job is scheduled (pending or active) for the given file and image type."""
        job_key = (rel_path, image_type)
        with QMutexLocker(self.mutex):
            # Check if job is currently active
            if job_key in self.active_jobs:
                return True
                
            # Check if job is in pending queue
            for job in self.pending_jobs:
                if job['relative_path'] == rel_path and job['image_type'] == image_type:
                    return True
                    
            return False
        
    def process_pending_jobs(self):
        """Process pending jobs up to the thread limit."""
        try:
            from preview import PreviewWorker
        except ImportError:
            print("Warning: PreviewWorker not available, cannot generate previews")
            return
            
        with QMutexLocker(self.mutex):
            # Start jobs up to the thread limit
            while (len(self.active_jobs) < self.max_threads and 
                   self.pending_jobs):
                job = self.pending_jobs.pop(0)
                
                job_key = (job["relative_path"], job["image_type"])
                
                print(f"Starting preview generation job: {job['relative_path']} ({job['image_type']})")
                
                worker = PreviewWorker(
                    self.darktable_cli_path,
                    job["raw_file"],
                    job["xmp_file"],
                    job["relative_path"],
                    job["image_type"],
                    self.preview_signals,
                    job["history_hash"],
                    self.preview_max_dimension,
                    self.preview_max_dimension,
                    retry_count=0,
                    max_retries=2,
                    enable_opencl=self.enable_opencl,
                )
                
                self.active_jobs[job_key] = worker
                self.thread_pool.start(worker)
                
    def on_preview_ready(self, rel_path, image_type, image_path):
        """Handle when a preview is ready."""
        # This is mainly for external listeners who want to know when previews are ready
        pass
    
    def on_preview_retry_requested(self, retry_worker):
        """Handle preview retry requests."""
        print(f"Cache manager retrying preview generation for {retry_worker.rel_path} ({retry_worker.image_type})")
        
        # Add a small delay before retrying (1 second) and start the retry worker
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1000, lambda: self.thread_pool.start(retry_worker))
        
    def on_preview_failed(self, rel_path, image_type, error_message):
        """Handle when preview generation fails."""
        print(f"Preview generation failed for {rel_path} ({image_type}): {error_message}")
        
    def on_job_finished(self, rel_path, image_type, preview_size):
        """Handle when a job is finished."""
        with QMutexLocker(self.mutex):
            job_key = (rel_path, image_type)
            if job_key in self.active_jobs:
                del self.active_jobs[job_key]
                
            self.completed_jobs += 1
            
        # Emit progress update
        self.cache_progress_updated.emit(self.completed_jobs, self.total_jobs)
        
        # Start next job if available
        self.process_pending_jobs()
        
        # Check if all jobs are complete
        if self.completed_jobs >= self.total_jobs:
            self.cache_generation_finished.emit()
            
    def cancel_all_jobs(self):
        """Cancel all pending and active jobs."""
        with QMutexLocker(self.mutex):
            self.pending_jobs.clear()
            
            # Cancel active jobs
            for worker in self.active_jobs.values():
                worker.cancel()
            self.active_jobs.clear()
            
            self.completed_jobs = 0
            self.total_jobs = 0
            

