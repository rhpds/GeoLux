import { useMode } from '../api/hooks';
import Badge from './Badge';

export default function ModeIndicator() {
  const { data } = useMode();
  const mode = data?.mode ?? 'live';
  return <Badge variant={mode}>{mode}</Badge>;
}
