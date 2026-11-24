// Chèn emoticon bằng cách nhập ký tự đặc biệt (Slide 30)
const MAP: [RegExp, string][] = [
  [/:-?\)/g, "🙂"], [/:-?D/g, "😃"], [/:-?\(/g, "🙁"], [/;-?\)/g, "😉"], [/:-?P/gi, "😛"],
  [/:-?O/g, "😮"], [/<3/g, "❤️"], [/:'\(/g, "😢"], [/\(y\)/gi, "👍"], [/:-?\*/g, "😘"], [/>:\(/g, "😠"],
];

export function emojify(text: string): string {
  // Không đổi các ký tự nằm trong URL (vd http://)
  return text
    .split(/(https?:\/\/[^\s]+)/g)
    .map((part) => (/^https?:\/\//.test(part) ? part : MAP.reduce((acc, [re, emo]) => acc.replace(re, emo), part)))
    .join("");
}
