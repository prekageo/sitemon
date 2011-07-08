select timestamp,count(*) from pages group by timestamp order by timestamp;
delete from pages where timestamp>'0000-00-00 00:00:00.000000' and timestamp<'0000-00-00 00:00:00.000000';
