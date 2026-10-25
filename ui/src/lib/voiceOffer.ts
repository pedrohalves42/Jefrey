/** Quando oferecer a voz que roda neste computador: a da nuvem falhou 2 vezes seguidas, a local nao esta instalada e a pessoa nao dispensou. */
export const VOICE_FAIL_EVENT = "jefrey:voice-cloud-failed"
export const DISMISS_KEY = "jefrey_voice_offer_dismissed"
export const FAILS_TO_OFFER = 2

export function shouldOffer(i: { failures: number; localInstalled: boolean; dismissed: boolean }): boolean {
  return i.failures >= FAILS_TO_OFFER && !i.localInstalled && !i.dismissed
}

export function offerText(sizeMb: number): string {
  return `A voz natural da internet não está respondendo. Quer baixar uma voz que funciona sem internet? São ${sizeMb} MB, uma vez só.`
}
