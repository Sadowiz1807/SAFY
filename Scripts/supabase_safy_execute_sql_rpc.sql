-- SAFY Supabase SQL RPC bridge
-- Run once in Supabase Dashboard -> SQL Editor.
-- SAFY calls this function only after Check Safety has passed in the sandbox.

create or replace function public.safy_execute_sql(sql text)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  if sql is null or length(trim(sql)) = 0 then
    return jsonb_build_object(
      'success', false,
      'error_code', 'SAFY_EMPTY_SQL',
      'error_message', 'SQL is empty'
    );
  end if;

  execute sql;

  return jsonb_build_object(
    'success', true,
    'status', 'executed',
    'message', 'SQL executed successfully'
  );
exception
  when others then
    return jsonb_build_object(
      'success', false,
      'error_code', SQLSTATE,
      'error_message', SQLERRM
    );
end;
$$;

revoke all on function public.safy_execute_sql(text) from public;
revoke all on function public.safy_execute_sql(text) from anon;
revoke all on function public.safy_execute_sql(text) from authenticated;
grant execute on function public.safy_execute_sql(text) to service_role;

-- Force PostgREST/Supabase Data API to see the function immediately.
notify pgrst, 'reload schema';
