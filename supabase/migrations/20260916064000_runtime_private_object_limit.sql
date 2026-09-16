-- Defense-in-depth: match the publisher's 45 MiB ceiling instead of the
-- bucket's larger nominal limit. NOT VALID deliberately tolerates historical
-- staged rows created before the chunking fix; new/updated rows are enforced.

alter table public.runtime_data_objects
  drop constraint if exists runtime_data_objects_size_bytes_check;

alter table public.runtime_data_objects
  add constraint runtime_data_objects_size_bytes_check
  check (size_bytes >= 0 and size_bytes <= 47185920)
  not valid;

comment on constraint runtime_data_objects_size_bytes_check on public.runtime_data_objects is
  '45 MiB runtime object ceiling; validate after stale pre-chunking generations are garbage-collected.';
