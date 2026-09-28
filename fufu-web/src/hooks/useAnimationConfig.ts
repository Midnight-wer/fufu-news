import { useMemo } from 'react';
import { anim, scaleByIntensity, type AnimConfig } from '@/config/animation';
import { useSettingsStore } from '@/stores/settingsStore';

export function useAnimationConfig(): AnimConfig {
  const intensity = useSettingsStore((s) => s.settings.effectIntensity);

  return useMemo(() => {
    const scaled: Record<string, Record<string, number>> = {};
    for (const key of Object.keys(anim) as (keyof AnimConfig)[]) {
      scaled[key] = scaleByIntensity(anim[key], intensity);
    }
    return scaled as AnimConfig;
  }, [intensity]);
}
