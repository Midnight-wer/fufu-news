/**
 * Animation state lock utility.
 *
 * Prevents re-triggering an animation while it is already running, and ensures
 * the same target cannot be acquired twice in succession.
 *
 * Usage:
 *   const lock = createAnimationLock(300);
 *   if (lock.tryAcquire('card-1')) {
 *     lock.acquire('card-1');
 *     // start animation...
 *     lock.release(); // auto-unlocks after duration
 *   }
 *   // On unmount: lock.reset();
 */

export interface AnimationLock {
  /** Check if a target can be acquired (not animating, not same target). */
  tryAcquire(target: string): boolean;
  /** Mark the target as acquired — call AFTER starting the animation. */
  acquire(target: string): void;
  /** Release the lock; auto-clears after `duration` ms. */
  release(): void;
  /** Immediately reset lock (e.g. on unmount or mouse leave). */
  reset(): void;
}

export function createAnimationLock(defaultDuration = 300): AnimationLock {
  let isAnimating = false;
  let currentTarget: string | null = null;
  let timerId: ReturnType<typeof setTimeout> | null = null;

  return {
    tryAcquire(target: string): boolean {
      if (isAnimating) return false;
      if (currentTarget === target) return false;
      return true;
    },

    acquire(target: string): void {
      isAnimating = true;
      currentTarget = target;
    },

    release(): void {
      if (timerId !== null) clearTimeout(timerId);
      timerId = setTimeout(() => {
        isAnimating = false;
        currentTarget = null;
        timerId = null;
      }, defaultDuration);
    },

    reset(): void {
      if (timerId !== null) {
        clearTimeout(timerId);
        timerId = null;
      }
      isAnimating = false;
      currentTarget = null;
    },
  };
}
