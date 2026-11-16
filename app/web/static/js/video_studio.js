/* iNew Video Studio: the layer editor on /editor/video (Fabric.js 7, app/web/static/vendor/fabric).
 *
 * Every layer (text, picture, shape) is a Fabric object whose coordinates are output pixels of the video
 * (1080 x 1920 for 9:16 ...); the canvas only zooms to fit the screen. The main picture (post video or photos, a
 * chosen picture, or a plain colour) is HTML under the transparent canvas, placed with the same maths as ffmpeg
 * (video_editor_service.frame_filter). To render, each layer is drawn alone at output size and sent as a PNG with
 * its position and time range; the server lays the PNGs over the framed picture with ffmpeg, so the video shows
 * exactly what the editor showed.
 */
(() => {
    'use strict';

    const CFG = JSON.parse(document.getElementById('studio-config').textContent);
    const $ = (id) => document.getElementById(id);
    const POST_ID = CFG.post_id;
    const FRAME = CFG.frame_sizes;
    const LANG_LABELS = Object.fromEntries(CFG.languages.map((l) => [l.code, l.labels]));
    const LAYER_PROPS = ['inewKind', 'inewName', 'inewRole', 'inewStart', 'inewEnd', 'inewBoxColor', 'inewBoxOpacity',
        'inewBoxPad', 'inewBoxRadius', 'inewRadius', 'inewBorder', 'inewBorderColor'];
    const FONTS = [
        { family: 'Be Vietnam Pro', label: 'Be Vietnam Pro', weights: [400, 700, 800] },
        { family: 'Montserrat', label: 'Montserrat', weights: [400, 600, 700, 800] },
        { family: 'Oswald', label: 'Oswald (chữ cao, gọn)', weights: [400, 600, 700] },
        { family: 'Playfair Display', label: 'Playfair Display (có chân)', weights: [400, 700, 800] },
        { family: 'Inter', label: 'Inter', weights: [400, 600, 700, 800] },
        { family: 'Arial', label: 'Arial', system: true },
        { family: 'Times New Roman', label: 'Times New Roman', system: true },
    ];
    const KIND_ICON = { text: '🔤', image: '🏞️', shape: '⬛' };
    const KIND_BAR = { text: 'bg-blue-500', image: 'bg-violet-500', shape: 'bg-amber-500' };

    fabric.FabricObject.customProperties = LAYER_PROPS;
    Object.assign(fabric.InteractiveFabricObject.ownDefaults, {
        originX: 'left', originY: 'top', transparentCorners: false, cornerStyle: 'circle', cornerSize: 11,
        cornerColor: '#ffffff', cornerStrokeColor: '#007AFF', borderColor: '#007AFF', borderScaleFactor: 1.5,
    });

    // ------------------------------------------------------------------ drawing helpers and layer classes
    function roundRectPath(ctx, x, y, w, h, r) {
        r = Math.max(0, Math.min(r, w / 2, h / 2));
        ctx.beginPath();
        ctx.moveTo(x + r, y);
        ctx.arcTo(x + w, y, x + w, y + h, r);
        ctx.arcTo(x + w, y + h, x, y + h, r);
        ctx.arcTo(x, y + h, x, y, r);
        ctx.arcTo(x, y, x + w, y, r);
        ctx.closePath();
    }

    function hexToRgba(hex, alpha) {
        const m = /^#?([0-9a-f]{6})$/i.exec(hex || '');
        if (!m) return `rgba(0,0,0,${alpha})`;
        const n = parseInt(m[1], 16);
        return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${alpha})`;
    }

    /** Text with an optional box behind it (colour, opacity, padding, rounded corners). */
    class InewText extends fabric.Textbox {
        static type = 'InewText';
        shouldCache() { return false; }  // the box reaches past the text: no clipped cache
        _render(ctx) {
            if (this.inewBoxColor && (this.inewBoxOpacity ?? 1) > 0) {
                const p = this.inewBoxPad || 0;
                const w = this.width + 2 * p, h = this.height + 2 * p;
                ctx.save();
                ctx.shadowColor = 'transparent';
                ctx.fillStyle = hexToRgba(this.inewBoxColor, this.inewBoxOpacity ?? 1);
                roundRectPath(ctx, -w / 2, -h / 2, w, h, this.inewBoxRadius || 0);
                ctx.fill();
                ctx.restore();
            }
            super._render(ctx);
        }
    }

    /** Picture with rounded corners (inewRadius, % of the short side) and a border (inewBorder, video pixels). */
    class InewImage extends fabric.FabricImage {
        static type = 'InewImage';
        shouldCache() { return false; }
        _render(ctx) {
            const w = this.width, h = this.height;
            const r = Math.min(w, h) * Math.min(50, this.inewRadius || 0) / 100;
            ctx.save();
            if (r > 0) { roundRectPath(ctx, -w / 2, -h / 2, w, h, r); ctx.clip(); }
            super._render(ctx);
            ctx.restore();
            const scale = Math.max(0.0001, (Math.abs(this.scaleX) + Math.abs(this.scaleY)) / 2);
            const bw = (this.inewBorder || 0) / scale;
            if (bw > 0) {
                ctx.save();
                ctx.shadowColor = 'transparent';
                ctx.lineWidth = bw;
                ctx.strokeStyle = this.inewBorderColor || '#ffffff';
                roundRectPath(ctx, -w / 2 + bw / 2, -h / 2 + bw / 2, w - bw, h - bw, Math.max(0, r - bw / 2));
                ctx.stroke();
                ctx.restore();
            }
        }
    }
    fabric.classRegistry.setClass(InewText);
    fabric.classRegistry.setClass(InewImage);

    // ------------------------------------------------------------------ state
    const hasPostMedia = !!(CFG.post_video || CFG.post_photos.length);
    const defaultBg = () => ({
        source: hasPostMedia ? 'post' : 'color', asset: null, fit: 'contain', fill: 'blur', color: '#0F172A',
        scale: 1, dx: 0, dy: 0,
    });
    const S = {
        aspect: '9:16', W: 1080, H: 1920, zoom: 0.3,
        bg: defaultBg(),
        trimStart: 0, trimEnd: 0,
        voice: { url: '', duration: 0 },
        lang: CFG.language,
        time: 0, playing: false, playFrom: 0, playPerf: 0,
        history: [], future: [], restoring: false, dirty: false,
        bgDrag: false, assets: CFG.assets || [], templates: CFG.templates || [],
        lastVideo: window.STUDIO_LAST_VIDEO || '', photoIndex: -1,
    };
    let canvas;
    const stage = $('stage'), stageWrap = $('stage-wrap');
    const bgVideo = $('bg-video'), bgImg = $('bg-img'), blurVideo = $('bg-blur-video'), blurImg = $('bg-blur-img');
    const voiceAudio = new Audio();
    voiceAudio.preload = 'auto';

    const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
    const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    const fmtTime = (t) => `${String(Math.floor(t / 60)).padStart(2, '0')}:${(t % 60).toFixed(1).padStart(4, '0')}`;
    const mediaUrl = (rel) => `/media/download?path=${encodeURIComponent(rel)}`;

    async function api(url, body, method = 'POST') {
        const opts = { method, headers: {} };
        if (body instanceof FormData) opts.body = body;
        else if (body !== undefined) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
        const res = await fetch(url, opts);
        let data = {};
        try { data = await res.json(); } catch (e) { /* not JSON */ }
        if (!res.ok || data.success === false) throw new Error(data.error || data.detail || `Lỗi máy chủ (${res.status})`);
        return data;
    }

    // ------------------------------------------------------------------ texts that follow the post and the language
    function labels(lang = S.lang) { return LANG_LABELS[lang] || LANG_LABELS.vi || Object.values(LANG_LABELS)[0]; }

    function roleText(role, lang = S.lang) {
        const lb = labels(lang);
        switch (role) {
            case 'header': return String(CFG.texts.header || lb.header).toUpperCase();
            case 'source': return `${lb.source}: ${CFG.texts.source}`.toUpperCase();
            case 'headline': return CFG.texts.headline || 'Tiêu đề bản tin';
            case 'tag': return lb.tag;
            case 'footer': return String(lb.footer).toUpperCase();
            default: return '';
        }
    }

    // ------------------------------------------------------------------ fonts
    async function loadFonts() {
        const jobs = [];
        for (const f of FONTS) {
            if (f.system) continue;
            for (const w of f.weights) jobs.push(document.fonts.load(`${w} 40px "${f.family}"`, 'Tiếng Việt Đường'));
        }
        await Promise.race([Promise.allSettled(jobs), new Promise((r) => setTimeout(r, 6000))]);
    }

    async function ensureFont(o) {
        try { await document.fonts.load(`${o.fontStyle === 'italic' ? 'italic ' : ''}${o.fontWeight} 40px "${o.fontFamily}"`, 'Tiếng Việt'); } catch (e) { /* system font */ }
        fabric.cache.clearFontCache(o.fontFamily);
        o.initDimensions();
        o.setCoords();
        canvas.requestRenderAll();
    }

    // ------------------------------------------------------------------ layer factories
    function makeText(text, opts = {}) {
        return new InewText(text, Object.assign({
            left: 60, top: 200, width: S.W - 120, originX: 'left', originY: 'top',
            fontFamily: 'Be Vietnam Pro', fontSize: 56, fontWeight: 700, fill: '#FFFFFF', textAlign: 'center',
            lineHeight: 1.18, stroke: '#000000', strokeWidth: 0, paintFirst: 'stroke', strokeUniform: false,
            inewKind: 'text', inewName: 'Chữ', inewRole: '', inewStart: 0, inewEnd: null,
            inewBoxColor: '', inewBoxOpacity: 1, inewBoxPad: 0, inewBoxRadius: 0,
        }, opts));
    }

    function makeRect(opts = {}) {
        return new fabric.Rect(Object.assign({
            left: 0, top: 0, width: 400, height: 120, originX: 'left', originY: 'top', fill: '#DC2626',
            rx: 0, ry: 0, stroke: '#FFFFFF', strokeWidth: 0, strokeUniform: true,
            inewKind: 'shape', inewName: 'Khối màu', inewRole: '', inewStart: 0, inewEnd: null,
        }, opts));
    }

    function softShadow() { return new fabric.Shadow({ color: 'rgba(0,0,0,0.65)', blur: 14, offsetX: 3, offsetY: 4 }); }

    function centerAt(o, cy) { o.set('top', Math.round(cy - o.getScaledHeight() / 2)); o.setCoords(); return o; }

    function fitWidth(o) {
        o.set('width', S.W * 3);
        o.initDimensions();
        let w = 0;
        for (let i = 0; i < o.textLines.length; i++) w = Math.max(w, o.getLineWidth(i));
        o.set('width', Math.ceil(w) + 4);
        o.initDimensions();
        o.setCoords();
        return o;
    }

    function placeCenter(o, dy = 0) {
        o.set({ left: Math.round((S.W - o.getScaledWidth()) / 2), top: Math.round((S.H - o.getScaledHeight()) / 2 + dy) });
        o.setCoords();
        return o;
    }

    const TEXT_PRESETS = {
        title: () => [placeCenter(makeText(roleText('headline'), {
            fontSize: Math.round(S.W * 0.075), fontWeight: 800, width: S.W - 120, stroke: '#000000',
            strokeWidth: Math.round(S.W * 0.006), shadow: softShadow(), inewName: 'Tiêu đề lớn', inewRole: 'headline',
        }), S.H * 0.15)],
        subtitle: () => [placeCenter(makeText('Phụ đề nội dung bản tin', {
            fontSize: Math.round(S.W * 0.046), fontWeight: 600, width: S.W - 200, inewBoxColor: '#000000',
            inewBoxOpacity: 0.62, inewBoxPad: 18, inewBoxRadius: 12, inewName: 'Phụ đề',
        }), S.H * 0.3)],
        badge: () => [placeCenter(fitWidth(makeText('NÓNG', {
            fontSize: Math.round(S.W * 0.04), fontWeight: 800, inewBoxColor: '#DC2626', inewBoxOpacity: 1,
            inewBoxPad: 14, inewBoxRadius: 10, inewName: 'Nhãn',
        })), -S.H * 0.3)],
        lower: () => {
            const h = Math.round(S.H * (S.H > S.W ? 0.09 : 0.14));
            const top = Math.round(S.H * 0.74);
            const band = makeRect({ left: 0, top, width: S.W, height: h, fill: '#0F172A', opacity: 0.9, inewName: 'Dải tít dưới' });
            const accent = makeRect({ left: 0, top, width: Math.round(S.W * 0.02), height: h, fill: '#DC2626', inewName: 'Vạch màu' });
            const text = makeText(roleText('headline'), {
                left: Math.round(S.W * 0.05), width: Math.round(S.W * 0.9), fontSize: Math.round(h * 0.36),
                fontWeight: 700, textAlign: 'left', inewName: 'Tít dải dưới', inewRole: 'headline',
            });
            centerAt(text, top + h / 2);
            return [band, accent, text];
        },
        plain: () => [placeCenter(makeText('Nội dung chữ', {
            fontSize: Math.round(S.W * 0.042), fontWeight: 400, width: S.W - 240, textAlign: 'left', inewName: 'Chữ thường',
        }))],
        source: () => [makeText(roleText('source'), {
            left: 40, top: 40, width: S.W - 80, fontSize: Math.round(S.W * 0.03), fontWeight: 700, textAlign: 'left',
            shadow: softShadow(), inewName: 'Nguồn tin', inewRole: 'source',
        })],
    };

    const SHAPE_PRESETS = {
        box: () => placeCenter(makeRect({ width: Math.round(S.W * 0.5), height: Math.round(S.W * 0.2), rx: 16, ry: 16, fill: '#DC2626', inewName: 'Khối màu' })),
        band: () => placeCenter(makeRect({ width: S.W, height: Math.round(S.H * 0.08), fill: '#1D4ED8', opacity: 0.9, inewName: 'Dải băng' })),
        line: () => placeCenter(makeRect({ width: Math.round(S.W * 0.6), height: 8, fill: '#F59E0B', inewName: 'Đường kẻ' })),
        circle: () => placeCenter(new fabric.Circle({
            radius: Math.round(S.W * 0.1), originX: 'left', originY: 'top', fill: '#10B981', stroke: '#FFFFFF',
            strokeWidth: 0, strokeUniform: true, inewKind: 'shape', inewName: 'Hình tròn', inewRole: '', inewStart: 0, inewEnd: null,
        })),
    };

    // ------------------------------------------------------------------ built-in layouts (the old theme overlay)
    const THEMES = {
        red: { name: '🔴 Đỏ · Tin nóng', head: '#B91C1C', src: '#FECACA', card: '#0F172A', border: '#EF4444', tag: '#F87171', foot: '#1E293B', footText: '#FCA5A5' },
        blue: { name: '🔵 Xanh · Sự kiện', head: '#1D4ED8', src: '#BFDBFE', card: '#0F172A', border: '#3B82F6', tag: '#60A5FA', foot: '#1E293B', footText: '#38BDF8' },
        gold: { name: '🟡 Vàng · Tiêu điểm', head: '#B45309', src: '#FEF08A', card: '#0F172A', border: '#EAB308', tag: '#FACC15', foot: '#1E293B', footText: '#FDE047' },
        dark: { name: '⚫ Đen · Tối giản', head: '#0F172A', src: '#CBD5E1', card: '#0F172A', border: '#64748B', tag: '#94A3B8', foot: '#020617', footText: '#E2E8F0' },
    };

    function themeObjects(key) {
        const c = THEMES[key];
        const W = S.W, H = S.H, out = [];
        const t = (role, opts) => makeText(roleText(role), Object.assign({ inewRole: role }, opts));
        if (key === 'clean') {
            const head = t('headline', {
                left: 60, width: W - 120, fontSize: Math.round(W * 0.05), fontWeight: 800,
                inewBoxColor: '#000000', inewBoxOpacity: 0.62, inewBoxPad: 20, inewBoxRadius: 14, inewName: 'Tiêu đề chính',
            });
            head.set('top', Math.round(H - head.getScaledHeight() - H * 0.12));
            out.push(head, t('source', {
                left: 40, top: 40, width: W - 80, fontSize: Math.round(W * 0.028), fontWeight: 700, textAlign: 'left',
                shadow: softShadow(), inewName: 'Nguồn tin',
            }));
            return out;
        }
        if (H > W) {  // 9:16, 4:5
            out.push(makeRect({ left: 0, top: 0, width: W, height: 220, fill: c.head, opacity: 0.94, inewName: 'Dải tít trên' }));
            out.push(centerAt(t('header', { left: 40, width: W - 80, fontSize: 60, fontWeight: 800, inewName: 'Tít trên' }), 75));
            out.push(centerAt(t('source', { left: 40, width: W - 80, fontSize: 34, fontWeight: 400, fill: c.src, inewName: 'Nguồn tin' }), 155));
            const cardTop = H - 480;
            out.push(makeRect({ left: 50, top: cardTop, width: W - 100, height: 340, rx: 24, ry: 24, fill: c.card, opacity: 0.92, stroke: c.border, strokeWidth: 3, inewName: 'Khung tiêu đề' }));
            out.push(centerAt(t('tag', { left: 90, width: W - 180, fontSize: 32, fontWeight: 800, fill: c.tag, inewName: 'Nhãn' }), cardTop + 45));
            out.push(t('headline', { left: 90, top: cardTop + 82, width: W - 180, fontSize: 48, fontWeight: 800, inewName: 'Tiêu đề chính' }));
            out.push(makeRect({ left: 0, top: H - 100, width: W, height: 100, fill: c.foot, opacity: 0.98, inewName: 'Dải chân' }));
            out.push(centerAt(t('footer', { left: 40, width: W - 80, fontSize: 30, fontWeight: 800, fill: c.footText, inewName: 'Chân trang' }), H - 50));
        } else if (H === W) {  // 1:1
            out.push(makeRect({ left: 0, top: 0, width: W, height: 140, fill: c.head, opacity: 0.94, inewName: 'Dải tít trên' }));
            out.push(centerAt(t('header', { left: 40, width: W - 80, fontSize: 48, fontWeight: 800, inewName: 'Tít trên' }), 50));
            out.push(centerAt(t('source', { left: 40, width: W - 80, fontSize: 28, fontWeight: 400, fill: c.src, inewName: 'Nguồn tin' }), 105));
            const cardTop = H - 300;
            out.push(makeRect({ left: 30, top: cardTop, width: W - 60, height: 240, rx: 18, ry: 18, fill: c.card, opacity: 0.92, stroke: c.border, strokeWidth: 3, inewName: 'Khung tiêu đề' }));
            out.push(t('headline', { left: 60, top: cardTop + 26, width: W - 120, fontSize: 38, fontWeight: 800, inewName: 'Tiêu đề chính' }));
            out.push(makeRect({ left: 0, top: H - 50, width: W, height: 50, fill: c.foot, opacity: 0.98, inewName: 'Dải chân' }));
            out.push(centerAt(t('footer', { left: 40, width: W - 80, fontSize: 24, fontWeight: 800, fill: c.footText, inewName: 'Chân trang' }), H - 25));
        } else {  // 16:9
            out.push(makeRect({ left: 0, top: 0, width: W, height: 120, fill: c.head, opacity: 0.94, inewName: 'Dải tít trên' }));
            out.push(centerAt(t('header', { left: 200, width: W * 0.45, fontSize: 48, fontWeight: 800, textAlign: 'left', inewName: 'Tít trên' }), 60));
            out.push(centerAt(t('source', { left: W * 0.55, width: W * 0.45 - 200, fontSize: 32, fontWeight: 400, textAlign: 'right', fill: c.src, inewName: 'Nguồn tin' }), 60));
            const barTop = H - 160;
            out.push(makeRect({ left: 0, top: barTop, width: W, height: 120, fill: c.card, opacity: 0.92, inewName: 'Dải tiêu đề' }));
            out.push(makeRect({ left: 0, top: barTop, width: W, height: 4, fill: c.border, inewName: 'Vạch màu' }));
            out.push(centerAt(t('headline', { left: 100, width: W - 200, fontSize: 40, fontWeight: 800, textAlign: 'left', inewName: 'Tiêu đề chính' }), barTop + 60));
            out.push(makeRect({ left: 0, top: H - 40, width: W, height: 40, fill: c.foot, opacity: 0.98, inewName: 'Dải chân' }));
            out.push(centerAt(t('footer', { left: 40, width: W - 80, fontSize: 22, fontWeight: 800, fill: c.footText, inewName: 'Chân trang' }), H - 20));
        }
        return out;
    }

    // ------------------------------------------------------------------ canvas and stage
    function fitStage() {
        const availW = Math.max(160, stageWrap.clientWidth - 24), availH = Math.max(160, stageWrap.clientHeight - 24);
        S.zoom = Math.min(availW / S.W, availH / S.H);
        const dw = Math.round(S.W * S.zoom), dh = Math.round(S.H * S.zoom);
        stage.style.width = `${dw}px`;
        stage.style.height = `${dh}px`;
        canvas.setDimensions({ width: dw, height: dh });
        canvas.setZoom(S.zoom);
        layoutBackground();
        canvas.requestRenderAll();
    }

    function setAspect(aspect, { remap = true, record = true } = {}) {
        if (!FRAME[aspect]) aspect = '9:16';
        const [W, H] = FRAME[aspect];
        const oldW = S.W, oldH = S.H;
        S.aspect = aspect;
        S.W = W;
        S.H = H;
        if (remap && canvas && (oldW !== W || oldH !== H)) remapObjects(oldW, oldH, W, H);
        document.querySelectorAll('[data-aspect]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.aspect === aspect)));
        if (canvas) { fitStage(); renderTimeline(); }
        if (record) changed();
    }

    /** Keep the layout when the frame changes: positions follow the frame, sizes shrink or grow with it. */
    function remapObjects(oW, oH, nW, nH) {
        const f = Math.min(nW / oW, nH / oH);
        for (const o of canvas.getObjects()) {
            const c = o.getCenterPoint();
            const nc = new fabric.Point(c.x / oW * nW, c.y / oH * nH);
            const wide = o.getScaledWidth() > oW * 0.7;
            if (o instanceof InewText) {
                o.set({
                    fontSize: Math.max(8, Math.round(o.fontSize * f)), width: Math.round(o.width * (wide ? nW / oW : f)),
                    strokeWidth: o.strokeWidth * f, inewBoxPad: (o.inewBoxPad || 0) * f,
                });
                o.initDimensions();
            } else if (o instanceof fabric.Rect && wide) {
                o.set({ scaleX: o.scaleX * nW / oW, scaleY: o.scaleY * f });
            } else {
                o.set({ scaleX: o.scaleX * f, scaleY: o.scaleY * f });
            }
            o.setPositionByOrigin(nc, 'center', 'center');
            o.setCoords();
        }
    }

    // ------------------------------------------------------------------ background (the main picture)
    function photos() { return CFG.post_photos.slice(0, 6); }

    function photoIndexAt(t) {
        const list = photos();
        if (!list.length) return -1;
        const per = Math.max(2.5, duration() / list.length);
        return Math.min(list.length - 1, Math.floor(t / per));
    }

    /** What is under the layers: {kind: 'video'|'img', src} or null for a plain colour. */
    function bgMedia() {
        if (S.bg.source === 'asset' && S.bg.asset) return { kind: 'img', src: S.bg.asset.url };
        if (S.bg.source === 'post') {
            if (CFG.post_video) return { kind: 'video', src: CFG.post_video.url };
            const i = photoIndexAt(S.time);
            if (i >= 0) return { kind: 'img', src: photos()[i].url };
        }
        return null;
    }

    function refreshBackground() {
        const m = bgMedia();
        $('bg-backdrop').style.background = S.bg.color;
        const showVideo = m && m.kind === 'video', showImg = m && m.kind === 'img';
        if (showVideo && bgVideo.dataset.src !== m.src) {
            bgVideo.src = m.src; blurVideo.src = m.src; bgVideo.dataset.src = m.src; bgVideo.loop = true; blurVideo.loop = true;
        }
        if (showImg && bgImg.dataset.src !== m.src) { bgImg.src = m.src; blurImg.src = m.src; bgImg.dataset.src = m.src; }
        const blur = S.bg.fill === 'blur';
        bgVideo.classList.toggle('hidden', !showVideo);
        blurVideo.classList.toggle('hidden', !(showVideo && blur));
        bgImg.classList.toggle('hidden', !showImg);
        blurImg.classList.toggle('hidden', !(showImg && blur));
        if (!showVideo) { bgVideo.pause(); blurVideo.pause(); }
        $('trim-box').classList.toggle('hidden', !showVideo);
        layoutBackground();
        refreshFrameControls();
    }

    function layoutBackground() {
        const z = S.zoom;
        const blurPx = `blur(${Math.max(3, 26 * z)}px)`;
        blurVideo.style.filter = blurPx;
        blurImg.style.filter = blurPx;
        for (const el of [bgVideo, bgImg]) {
            if (el.classList.contains('hidden')) continue;
            const iw = el.videoWidth || el.naturalWidth, ih = el.videoHeight || el.naturalHeight;
            if (!iw || !ih) continue;
            const f = (S.bg.fit === 'contain' ? Math.min : Math.max)(S.W / iw, S.H / ih) * S.bg.scale;
            const w = Math.max(2, Math.trunc(iw * f / 2) * 2), h = Math.max(2, Math.trunc(ih * f / 2) * 2);
            const x = (S.W - w) / 2 + S.bg.dx, y = (S.H - h) / 2 + S.bg.dy;
            Object.assign(el.style, { left: `${x * z}px`, top: `${y * z}px`, width: `${w * z}px`, height: `${h * z}px` });
        }
    }

    function videoTimeAt(t) {
        const d = bgVideo.duration || 0;
        let vt = S.trimStart + t;
        if (d > 0 && vt >= d) vt %= d;
        return vt;
    }

    function seekMedia() {
        if (!bgVideo.classList.contains('hidden') && bgVideo.readyState >= 1) {
            const vt = videoTimeAt(S.time);
            if (Math.abs(bgVideo.currentTime - vt) > 0.04) { bgVideo.currentTime = vt; blurVideo.currentTime = vt; }
        }
        if (S.bg.source === 'post' && !CFG.post_video) {
            const i = photoIndexAt(S.time);
            if (i !== S.photoIndex) { S.photoIndex = i; refreshBackground(); }
        }
    }

    function refreshFrameControls() {
        document.querySelectorAll('[data-bg-source]').forEach((b) => {
            b.setAttribute('aria-pressed', String(b.dataset.bgSource === S.bg.source));
            b.disabled = (b.dataset.bgSource === 'post' && !hasPostMedia) || (b.dataset.bgSource === 'asset' && !S.bg.asset);
            b.classList.toggle('opacity-40', b.disabled);
        });
        document.querySelectorAll('[data-fit]').forEach((b) => b.setAttribute('aria-pressed',
            String(b.dataset.fit === S.bg.fit && b.dataset.fill === S.bg.fill)));
        $('bg-color').value = S.bg.color;
        $('bg-scale').value = Math.round(S.bg.scale * 100);
        $('bg-scale-value').textContent = `${Math.round(S.bg.scale * 100)}%`;
        $('trim-start').value = S.trimStart || 0;
        $('trim-end').value = S.trimEnd > S.trimStart ? S.trimEnd : '';
        const note = $('bg-source-note');
        if (S.bg.source === 'post') note.textContent = CFG.post_video ? 'Dùng video gốc của bài.' : `Trình chiếu ${photos().length} ảnh của bài.`;
        else if (S.bg.source === 'asset') note.textContent = 'Dùng ảnh đã chọn (thẻ Ảnh · AI, nút "Nền").';
        else note.textContent = hasPostMedia ? 'Nền một màu, không dùng video, ảnh của bài.' : 'Bài này không có video, ảnh: dùng nền màu hoặc chọn ảnh làm nền.';
    }

    // ------------------------------------------------------------------ time, playback
    function estimateVoiceSeconds() {
        const words = $('input-voiceover-text').value.trim().split(/\s+/).filter(Boolean).length;
        return words / 2.7;
    }

    function duration() {
        if (S.trimEnd > S.trimStart) return S.trimEnd - S.trimStart;
        return Math.max(10, (S.voice.duration || estimateVoiceSeconds()) + 0.8);
    }

    function visibleAt(o, t) { return t >= (o.inewStart || 0) - 1e-6 && (o.inewEnd == null || t < o.inewEnd); }

    /** Layers outside their time range are hidden, except the one being edited (playback clears the selection). */
    function applyTime() {
        const active = canvas.getActiveObjects();
        for (const o of canvas.getObjects()) o.visible = visibleAt(o, S.time) || active.includes(o);
        canvas.requestRenderAll();
    }

    function setTime(t, fromPlayback = false) {
        S.time = clamp(t, 0, duration());
        applyTime();
        $('time-label').textContent = `${fmtTime(S.time)} / ${fmtTime(duration())}`;
        const ph = $('tl-playhead');
        if (ph) ph.style.left = `${(S.time / duration()) * 100}%`;
        if (!fromPlayback) seekMedia();
        else if (S.bg.source === 'post' && !CFG.post_video) seekMedia();
    }

    function play() {
        if (S.playing) { pause(); return; }
        if (S.time >= duration() - 0.05) setTime(0);
        canvas.discardActiveObject();
        S.playing = true;
        S.playFrom = S.time;
        S.playPerf = performance.now();
        $('btn-play').textContent = '⏸ Dừng';
        if (!bgVideo.classList.contains('hidden')) {
            const orig = parseFloat($('input-orig-vol').value) || 0;
            bgVideo.currentTime = videoTimeAt(S.time);
            blurVideo.currentTime = bgVideo.currentTime;
            bgVideo.volume = clamp(orig, 0, 1);
            bgVideo.muted = orig <= 0.001;
            bgVideo.play().catch(() => { });
            blurVideo.play().catch(() => { });
        }
        if (S.voice.url && S.time < S.voice.duration) {
            voiceAudio.currentTime = S.time;
            voiceAudio.volume = clamp(parseFloat($('input-voice-vol').value) || 1, 0, 1);
            voiceAudio.play().catch(() => { });
        }
        requestAnimationFrame(tick);
    }

    function tick(now) {
        if (!S.playing) return;
        const t = S.playFrom + (now - S.playPerf) / 1000;
        if (t >= duration()) { setTime(duration(), true); pause(); return; }
        setTime(t, true);
        if (!bgVideo.paused) {
            const want = videoTimeAt(t);
            if (Math.abs(bgVideo.currentTime - want) > 0.4) { bgVideo.currentTime = want; blurVideo.currentTime = want; }
        }
        requestAnimationFrame(tick);
    }

    function pause() {
        S.playing = false;
        bgVideo.pause();
        blurVideo.pause();
        voiceAudio.pause();
        $('btn-play').textContent = '▶ Phát';
    }

    // ------------------------------------------------------------------ history (undo / redo) and saving
    function cleanObjects(objects) {
        for (const o of objects) {
            if (typeof o.src === 'string' && o.src.startsWith(location.origin)) o.src = o.src.slice(location.origin.length);
            o.visible = true;
            if (Array.isArray(o.objects)) cleanObjects(o.objects);
        }
        return objects;
    }

    function layerObjects() { return cleanObjects(canvas.toObject().objects); }

    function snapshot() { return JSON.stringify({ aspect: S.aspect, bg: S.bg, trim: [S.trimStart, S.trimEnd], objects: layerObjects() }); }

    function markDirty() { S.dirty = true; }

    function changed() {
        if (S.restoring) return;
        const snap = snapshot();
        if (S.history[S.history.length - 1] !== snap) {
            S.history.push(snap);
            if (S.history.length > 80) S.history.shift();
            S.future = [];
            markDirty();
        }
        updateUndoButtons();
        renderTimeline();
        setTime(S.time);
    }

    function updateUndoButtons() {
        $('btn-undo').disabled = S.history.length < 2;
        $('btn-redo').disabled = !S.future.length;
    }

    async function restore(snap) {
        S.restoring = true;
        try {
            const d = JSON.parse(snap);
            S.bg = Object.assign(defaultBg(), d.bg);
            [S.trimStart, S.trimEnd] = d.trim || [0, 0];
            setAspect(d.aspect, { remap: false, record: false });
            await canvas.loadFromJSON({ objects: d.objects });
        } finally {
            S.restoring = false;
        }
        afterLoad();
    }

    async function undo() {
        if (S.history.length < 2) return;
        S.future.push(S.history.pop());
        await restore(S.history[S.history.length - 1]);
        markDirty();
    }

    async function redo() {
        if (!S.future.length) return;
        const snap = S.future.pop();
        S.history.push(snap);
        await restore(snap);
        markDirty();
    }

    function afterLoad() {
        for (const o of canvas.getObjects()) {
            if (o instanceof InewText) ensureFont(o);
            o.setCoords();
        }
        refreshBackground();
        renderTimeline();
        renderProps();
        updateUndoButtons();
        setTime(S.time);
    }

    function voiceSettings() {
        return {
            language: S.lang, voice_key: $('select-voice').value, text: $('input-voiceover-text').value,
            speed: parseFloat($('input-voice-speed').value) || 1, voice_volume: parseFloat($('input-voice-vol').value),
            original_volume: parseFloat($('input-orig-vol').value),
        };
    }

    function projectData(withVoice = true) {
        const d = { version: 1, aspect: S.aspect, bg: { ...S.bg }, trim: { start: S.trimStart, end: S.trimEnd }, objects: layerObjects() };
        if (withVoice) d.voice = voiceSettings();
        return d;
    }

    async function loadProject(p, { fromTemplate = false } = {}) {
        S.restoring = true;
        try {
            if (p.bg) S.bg = Object.assign(defaultBg(), p.bg);
            if (!fromTemplate && p.trim) { S.trimStart = +p.trim.start || 0; S.trimEnd = +p.trim.end || 0; }
            setAspect(p.aspect || '9:16', { remap: false, record: false });
            if (S.bg.source === 'post' && !hasPostMedia) S.bg.source = 'color';
            if (!fromTemplate && p.voice) applyVoiceSettings(p.voice);
            const objects = (p.objects || []).map((o) => (fromTemplate && o.inewRole && roleText(o.inewRole)) ? { ...o, text: roleText(o.inewRole) } : o);
            await canvas.loadFromJSON({ objects });
        } finally {
            S.restoring = false;
        }
        afterLoad();
    }

    function applyVoiceSettings(v) {
        if (v.language && LANG_LABELS[v.language]) { S.lang = v.language; $('select-language').value = v.language; fillVoiceSelect(); }
        if (v.voice_key && [...$('select-voice').options].some((o) => o.value === v.voice_key)) $('select-voice').value = v.voice_key;
        if (typeof v.text === 'string' && v.text.trim()) $('input-voiceover-text').value = v.text;
        if (v.speed) $('input-voice-speed').value = v.speed;
        if (v.voice_volume != null) $('input-voice-vol').value = v.voice_volume;
        if (v.original_volume != null) $('input-orig-vol').value = v.original_volume;
        refreshVoiceLabels();
    }

    async function saveDraft() {
        const btn = $('btn-save-draft');
        btn.disabled = true;
        try {
            await api('/api/studio/project', { post_id: POST_ID, design: projectData() });
            S.dirty = false;
            flash(btn, '✓ Đã lưu nháp');
        } catch (e) {
            alert(`Chưa lưu được: ${e.message}`);
        } finally {
            btn.disabled = false;
        }
    }

    function flash(btn, text) {
        const old = btn.textContent;
        btn.textContent = text;
        setTimeout(() => { btn.textContent = old; }, 1600);
    }

    // ------------------------------------------------------------------ adding and changing layers
    function addLayers(objs, { select = true } = {}) {
        for (const o of objs) {
            if (o.inewStart == null) o.inewStart = 0;
            canvas.add(o);
        }
        if (select && objs.length) canvas.setActiveObject(objs[objs.length - 1]);
        changed();
    }

    async function addImageLayer(asset, { ai = false } = {}) {
        const img = await InewImage.fromURL(asset.url, {}, {
            originX: 'left', originY: 'top', inewKind: 'image', inewName: ai ? 'Ảnh AI' : 'Ảnh', inewRole: '',
            inewStart: 0, inewEnd: null, inewRadius: 0, inewBorder: 0, inewBorderColor: '#FFFFFF',
        });
        const s = Math.min(S.W * 0.8 / img.width, S.H * 0.5 / img.height);
        img.scale(s);
        placeCenter(img, -S.H * 0.06);
        const objs = [img];
        if (ai) objs.push(aiLabel(img.left + 16, img.top + img.getScaledHeight() - 16));
        addLayers(objs, { select: false });
        canvas.setActiveObject(img);
        renderProps();
    }

    function aiLabel(left, bottom) {
        const label = fitWidth(makeText('Ảnh minh hoạ AI', {
            fontSize: Math.round(S.W * 0.024), fontWeight: 600, inewBoxColor: '#000000', inewBoxOpacity: 0.55,
            inewBoxPad: 8, inewBoxRadius: 6, inewName: 'Nhãn ảnh AI',
        }));
        label.set({ left: Math.round(left + 8), top: Math.round(bottom - label.getScaledHeight() - 8) });
        label.setCoords();
        return label;
    }

    function useAsBackground(asset) {
        S.bg.source = 'asset';
        S.bg.asset = { rel_path: asset.rel_path, url: asset.url };
        S.bg.dx = 0; S.bg.dy = 0; S.bg.scale = 1;
        refreshBackground();
        if (asset.kind === 'ai') addLayers([aiLabel(30, S.H - 30)], { select: false });
        else changed();
        selectTab('frame');
    }

    async function duplicateSelected() {
        const objs = canvas.getActiveObjects();
        if (!objs.length) return;
        canvas.discardActiveObject();
        const copies = [];
        for (const o of objs) {
            const c = await o.clone();
            c.set({ left: o.left + 30, top: o.top + 30, inewName: `${o.inewName || 'Lớp'} (bản sao)` });
            copies.push(c);
        }
        addLayers(copies);
    }

    function removeSelected() {
        const objs = canvas.getActiveObjects();
        if (!objs.length) return;
        canvas.discardActiveObject();
        objs.forEach((o) => canvas.remove(o));
        changed();
        renderProps();
    }

    function selectObject(o) {
        if (!o) return;
        if (!visibleAt(o, S.time)) setTime((o.inewStart || 0) + 0.01);
        canvas.setActiveObject(o);
        canvas.requestRenderAll();
        renderProps();
        renderTimeline();
    }

    /** Corner-scaling a text box changes its scale; turn that into font size and width so the panel stays true. */
    function bakeTextScale(o) {
        if (!(o instanceof InewText) || (Math.abs(o.scaleX - 1) < 1e-3 && Math.abs(o.scaleY - 1) < 1e-3)) return;
        const sy = o.scaleY;
        o.set({
            fontSize: Math.max(6, Math.round(o.fontSize * sy)), width: Math.max(20, o.width * o.scaleX),
            strokeWidth: o.strokeWidth * sy, inewBoxPad: (o.inewBoxPad || 0) * sy, inewBoxRadius: (o.inewBoxRadius || 0) * sy,
            scaleX: 1, scaleY: 1,
        });
        o.initDimensions();
        o.setCoords();
    }

    // ------------------------------------------------------------------ properties panel
    const field = (label, inner) => `<label class="block"><span class="block text-[11px] font-semibold text-[#3C3C43] mb-0.5">${label}</span>${inner}</label>`;
    const inputCls = 'w-full px-2 py-1 rounded-lg bg-white border border-[#D9D9DE] text-xs text-[#1C1C1E]';
    const btnCls = 'px-2 py-1.5 rounded-lg border border-[#D9D9DE] bg-white text-[11px] font-semibold text-[#1C1C1E] hover:bg-[#EFEFF4]';
    const num = (prop, value, attrs = '') => `<input type="number" data-prop="${prop}" value="${value}" ${attrs} class="${inputCls} font-mono">`;
    const color = (prop, value) => `<input type="color" data-prop="${prop}" value="${esc(value)}" class="h-7 w-full rounded border border-[#D9D9DE] bg-white">`;
    const range = (prop, value, min, max, step) => `<input type="range" data-prop="${prop}" value="${value}" min="${min}" max="${max}" step="${step}" class="w-full accent-blue-500">`;
    const check = (prop, on, label) => `<label class="flex items-center gap-1.5 text-[11px] text-[#3C3C43]"><input type="checkbox" data-prop="${prop}" ${on ? 'checked' : ''}> ${label}</label>`;
    const toHex = (c, fallback = '#ffffff') => (/^#[0-9a-f]{6}$/i.test(c || '') ? c : fallback);

    function renderProps() {
        const body = $('props-body'), empty = $('props-empty');
        // A focused field fires its change event when it is removed: let that run now, not in the middle of
        // replacing the panel (which throws "The node to be removed is no longer a child of this node").
        if (body.contains(document.activeElement)) document.activeElement.blur();
        const objs = canvas ? canvas.getActiveObjects() : [];
        if (!objs.length) { body.hidden = true; empty.hidden = false; body.innerHTML = ''; return; }
        empty.hidden = true;
        body.hidden = false;
        if (objs.length > 1) {
            body.innerHTML = `<p class="font-semibold text-[#1C1C1E] mb-2">${objs.length} lớp đang chọn</p>
                <div class="grid grid-cols-2 gap-1.5"><button type="button" data-act="duplicate" class="${btnCls}">⧉ Nhân bản</button>
                <button type="button" data-act="delete" class="${btnCls} text-red-600">🗑 Xoá</button></div>`;
            return;
        }
        const o = objs[0];
        const kind = o.inewKind || 'shape';
        const end = o.inewEnd == null ? '' : (+o.inewEnd).toFixed(1);
        let html = `<div class="space-y-2.5">
            <div class="flex items-center gap-2"><span class="text-base">${KIND_ICON[kind] || '⬛'}</span>
                <input type="text" data-prop="inewName" value="${esc(o.inewName || '')}" class="${inputCls} font-semibold"></div>`;
        if (kind === 'text') {
            const fonts = FONTS.map((f) => `<option value="${esc(f.family)}" ${f.family === o.fontFamily ? 'selected' : ''}>${esc(f.label)}</option>`).join('');
            const weights = [[400, 'Thường'], [600, 'Vừa'], [700, 'Đậm'], [800, 'Rất đậm']]
                .map(([w, l]) => `<option value="${w}" ${+o.fontWeight === w ? 'selected' : ''}>${l}</option>`).join('');
            const align = ['left', 'center', 'right'].map((a, i) => `<button type="button" data-align="${a}" class="${btnCls} ${o.textAlign === a ? 'ring-2 ring-blue-500' : ''}">${['⇤ Trái', '↔ Giữa', '⇥ Phải'][i]}</button>`).join('');
            html += `
            ${field('Nội dung', `<textarea data-prop="text" rows="3" class="${inputCls} leading-relaxed custom-scroll">${esc(o.text)}</textarea>`)}
            <div class="grid grid-cols-2 gap-1.5">
                ${field('Phông chữ', `<select data-prop="fontFamily" class="${inputCls}">${fonts}</select>`)}
                ${field('Độ đậm', `<select data-prop="fontWeight" class="${inputCls}">${weights}</select>`)}
            </div>
            <div class="grid grid-cols-3 gap-1.5 items-end">
                ${field('Cỡ chữ', num('fontSize', Math.round(o.fontSize), 'min="8" max="400"'))}
                ${field('Màu chữ', color('fill', toHex(o.fill)))}
                ${field('Giãn dòng', num('lineHeight', (+o.lineHeight).toFixed(2), 'min="0.7" max="3" step="0.05"'))}
            </div>
            <div class="grid grid-cols-3 gap-1">${align}</div>
            <div class="flex flex-wrap gap-1.5">
                <button type="button" data-act="italic" class="${btnCls} ${o.fontStyle === 'italic' ? 'ring-2 ring-blue-500' : ''}"><i>I</i> Nghiêng</button>
                <button type="button" data-act="upper" class="${btnCls}">AA Viết hoa</button>
                <button type="button" data-act="fit" class="${btnCls}">↔ Vừa chữ</button>
            </div>
            <div class="p-2 rounded-lg bg-[#F2F2F7] space-y-1.5">
                <div class="grid grid-cols-2 gap-1.5 items-end">
                    ${field('Viền chữ', num('strokeWidth', Math.round(o.strokeWidth || 0), 'min="0" max="40"'))}
                    ${field('Màu viền', color('stroke', toHex(o.stroke, '#000000')))}
                </div>
                ${check('shadow', !!o.shadow, 'Đổ bóng chữ')}
            </div>
            <div class="p-2 rounded-lg bg-[#F2F2F7] space-y-1.5">
                ${check('inewBox', !!o.inewBoxColor, 'Nền sau chữ')}
                <div class="grid grid-cols-2 gap-1.5 items-end ${o.inewBoxColor ? '' : 'opacity-40 pointer-events-none'}">
                    ${field('Màu nền', color('inewBoxColor', toHex(o.inewBoxColor, '#000000')))}
                    ${field(`Độ đậm nền ${Math.round((o.inewBoxOpacity ?? 1) * 100)}%`, range('inewBoxOpacity', o.inewBoxOpacity ?? 1, 0, 1, 0.05))}
                    ${field('Đệm', num('inewBoxPad', Math.round(o.inewBoxPad || 0), 'min="0" max="200"'))}
                    ${field('Bo góc', num('inewBoxRadius', Math.round(o.inewBoxRadius || 0), 'min="0" max="200"'))}
                </div>
            </div>`;
        } else if (kind === 'image') {
            html += `
            ${field(`Bo góc ${Math.round(o.inewRadius || 0)}%`, range('inewRadius', o.inewRadius || 0, 0, 50, 1))}
            <div class="grid grid-cols-2 gap-1.5 items-end">
                ${field('Viền ảnh', num('inewBorder', Math.round(o.inewBorder || 0), 'min="0" max="80"'))}
                ${field('Màu viền', color('inewBorderColor', toHex(o.inewBorderColor)))}
            </div>
            <button type="button" data-act="flip" class="${btnCls}">⇋ Lật ngang</button>`;
        } else {
            const isRect = o instanceof fabric.Rect;
            html += `
            <div class="grid grid-cols-2 gap-1.5 items-end">
                ${field('Màu', color('fill', toHex(o.fill, '#DC2626')))}
                ${isRect ? field('Bo góc', num('rx', Math.round(o.rx || 0), 'min="0" max="500"')) : '<span></span>'}
                ${field('Viền', num('strokeWidth', Math.round(o.strokeWidth || 0), 'min="0" max="60"'))}
                ${field('Màu viền', color('stroke', toHex(o.stroke)))}
            </div>`;
        }
        html += `
            ${field(`Độ trong suốt: hiện ${Math.round((o.opacity ?? 1) * 100)}%`, range('opacity', o.opacity ?? 1, 0.05, 1, 0.05))}
            <div class="p-2 rounded-lg bg-blue-50 border border-blue-100 space-y-1.5">
                <p class="text-[11px] font-semibold text-[#3C3C43]">⏱️ Thời gian hiện (giây)</p>
                <div class="grid grid-cols-2 gap-1.5">
                    ${field('Từ', num('inewStart', (+o.inewStart || 0).toFixed(1), 'min="0" step="0.1"'))}
                    ${field('Đến', `<input type="number" data-prop="inewEnd" value="${end}" min="0" step="0.1" placeholder="hết video" class="${inputCls} font-mono">`)}
                </div>
                ${check('inewAll', o.inewEnd == null && !(o.inewStart > 0), 'Hiện suốt video')}
            </div>
            <div class="grid grid-cols-2 gap-1.5">
                ${field('X', num('left', Math.round(o.left)))}${field('Y', num('top', Math.round(o.top)))}
            </div>
            <div class="grid grid-cols-2 gap-1.5">
                <button type="button" data-act="centerH" class="${btnCls}">↔ Giữa ngang</button>
                <button type="button" data-act="centerV" class="${btnCls}">↕ Giữa dọc</button>
                <button type="button" data-act="forward" class="${btnCls}">⬆ Lên trên</button>
                <button type="button" data-act="backward" class="${btnCls}">⬇ Xuống dưới</button>
                <button type="button" data-act="duplicate" class="${btnCls}">⧉ Nhân bản</button>
                <button type="button" data-act="delete" class="${btnCls} text-red-600">🗑 Xoá lớp</button>
            </div>
        </div>`;
        body.innerHTML = html;
    }

    function applyProp(o, prop, el) {
        const v = el.type === 'checkbox' ? el.checked : el.value;
        switch (prop) {
            case 'text': o.set('text', v); break;
            case 'inewName': o.set('inewName', v); renderTimeline(); return;
            case 'fontFamily': o.set('fontFamily', v); ensureFont(o); break;
            case 'fontWeight': o.set('fontWeight', +v); ensureFont(o); break;
            case 'fontSize': if (+v >= 4) o.set('fontSize', +v); break;
            case 'lineHeight': if (+v > 0.3) o.set('lineHeight', +v); break;
            case 'strokeWidth': o.set('strokeWidth', Math.max(0, +v || 0)); break;
            case 'shadow': o.set('shadow', v ? softShadow() : null); break;
            case 'inewBox': o.set('inewBoxColor', v ? (o.inewBoxColor || '#000000') : ''); if (v && !o.inewBoxPad) o.set('inewBoxPad', 14); break;
            case 'inewBoxOpacity': case 'inewRadius': case 'opacity': o.set(prop, +v); break;
            case 'inewBoxPad': case 'inewBoxRadius': case 'inewBorder': o.set(prop, Math.max(0, +v || 0)); break;
            case 'rx': o.set({ rx: Math.max(0, +v || 0), ry: Math.max(0, +v || 0) }); break;
            case 'left': case 'top': o.set(prop, +v || 0); break;
            case 'inewStart': o.set('inewStart', clamp(+v || 0, 0, duration())); break;
            case 'inewEnd': o.set('inewEnd', v === '' ? null : Math.max((o.inewStart || 0) + 0.1, +v)); break;
            case 'inewAll': if (v) o.set({ inewStart: 0, inewEnd: null }); break;
            default: o.set(prop, v);
        }
        if (o instanceof InewText) o.initDimensions();
        o.dirty = true;
        o.setCoords();
        canvas.requestRenderAll();
        markDirty();
    }

    function onPropsInput(e) {
        const el = e.target.closest('[data-prop]');
        const o = canvas.getActiveObject();
        if (!el || !o || canvas.getActiveObjects().length !== 1) return;
        applyProp(o, el.dataset.prop, el);
        if (['inewStart', 'inewEnd'].includes(el.dataset.prop)) renderTimeline();
    }

    function onPropsChange(e) {
        const el = e.target.closest('[data-prop]');
        if (!el) return;
        if (['inewAll', 'inewBox', 'shadow', 'inewStart', 'inewEnd'].includes(el.dataset.prop) || el.type === 'range') renderProps();
        changed();
    }

    function onPropsClick(e) {
        const btn = e.target.closest('button');
        if (!btn) return;
        const o = canvas.getActiveObject();
        if (!o) return;
        if (btn.dataset.align) { o.set('textAlign', btn.dataset.align); o.dirty = true; changed(); renderProps(); return; }
        const act = btn.dataset.act;
        if (act === 'delete') { removeSelected(); return; }
        if (act === 'duplicate') { duplicateSelected(); return; }
        if (act === 'italic') { o.set('fontStyle', o.fontStyle === 'italic' ? 'normal' : 'italic'); ensureFont(o); }
        if (act === 'upper') o.set('text', o.text.toLocaleUpperCase('vi'));
        if (act === 'fit') fitWidth(o);
        if (act === 'flip') o.set('flipX', !o.flipX);
        if (act === 'centerH') o.setPositionByOrigin(new fabric.Point(S.W / 2, o.getCenterPoint().y), 'center', 'center');
        if (act === 'centerV') o.setPositionByOrigin(new fabric.Point(o.getCenterPoint().x, S.H / 2), 'center', 'center');
        if (act === 'forward') canvas.bringObjectForward(o);
        if (act === 'backward') canvas.sendObjectBackwards(o);
        if (o instanceof InewText) o.initDimensions();
        o.setCoords();
        canvas.requestRenderAll();
        changed();
        renderProps();
    }

    // ------------------------------------------------------------------ timeline
    function renderTimeline() {
        if (!canvas) return;
        const dur = duration();
        const step = dur <= 20 ? 1 : dur <= 60 ? 5 : 10;
        let ticks = '';
        for (let s = 0; s <= dur + 1e-6; s += step) {
            ticks += `<span class="absolute bottom-0 h-2 border-l border-[#AEAEB2]" style="left:${(s / dur) * 100}%"></span>`;
            if ((s / step) % (step === 1 ? 2 : 1) === 0) ticks += `<span class="absolute top-0 -translate-x-1/2 text-[10px] text-[#8A8A8E] font-mono" style="left:${(s / dur) * 100}%">${s}s</span>`;
        }
        const active = canvas.getActiveObjects();
        const objs = canvas.getObjects();
        let rows = '';
        for (let i = objs.length - 1; i >= 0; i--) {
            const o = objs[i];
            const start = clamp(o.inewStart || 0, 0, dur), end = o.inewEnd == null ? dur : clamp(o.inewEnd, start, dur);
            const label = o.inewKind === 'text' ? (o.text || '').replace(/\s+/g, ' ').slice(0, 40) : (o.inewName || '');
            rows += `<div class="tl-row flex items-center h-7" data-idx="${i}" aria-selected="${active.includes(o)}">
                <div class="tl-name w-36 shrink-0 truncate pr-2 cursor-pointer text-[#3C3C43]">${KIND_ICON[o.inewKind] || '⬛'} ${esc(o.inewName || 'Lớp')}</div>
                <div class="tl-track relative flex-1 h-5 rounded bg-[#F2F2F7]">
                    <div class="tl-bar absolute top-0 bottom-0 rounded ${KIND_BAR[o.inewKind] || 'bg-amber-500'} text-white text-[10px] leading-5 px-2 truncate cursor-grab"
                        style="left:${(start / dur) * 100}%;width:${Math.max(0.5, ((end - start) / dur) * 100)}%">
                        <span class="tl-handle" data-side="start" style="left:0"></span>${esc(label)}<span class="tl-handle" data-side="end" style="right:0"></span>
                    </div>
                </div></div>`;
        }
        const bgName = S.bg.source === 'color' ? '🎨 Nền màu' : S.bg.source === 'asset' ? '🖼️ Ảnh nền' : (CFG.post_video ? '🎞️ Video nền' : '🖼️ Ảnh của bài');
        $('timeline').innerHTML = `
            <div class="flex items-end h-6"><div class="w-36 shrink-0 text-[10px] text-[#8A8A8E]">${S.voice.duration ? '' : 'Độ dài ước tính'}</div>
                <div id="tl-ruler" class="relative flex-1 h-6 border-b border-[#D9D9DE] cursor-pointer">${ticks}</div></div>
            <div class="relative">
                ${rows || '<p class="py-3 text-center text-[#8A8A8E]">Chưa có lớp nào: thêm chữ, ảnh hoặc áp một mẫu.</p>'}
                <div class="flex items-center h-7"><div class="w-36 shrink-0 truncate pr-2 text-[#8A8A8E]">${bgName}</div>
                    <div class="relative flex-1 h-5 rounded bg-slate-300"></div></div>
                <div class="absolute top-0 bottom-0 pointer-events-none" style="left:9rem;right:0">
                    <div id="tl-playhead" class="absolute top-0 bottom-0 w-0.5 bg-red-500" style="left:${(S.time / dur) * 100}%"></div>
                </div>
            </div>`;
        $('duration-note').textContent = S.voice.duration ? '' : '(độ dài ước tính: bấm "Tạo giọng đọc để nghe thử" để biết đúng)';
        $('time-label').textContent = `${fmtTime(S.time)} / ${fmtTime(dur)}`;
    }

    function trackTime(track, clientX) {
        const r = track.getBoundingClientRect();
        return clamp((clientX - r.left) / r.width, 0, 1) * duration();
    }

    function onTimelineDown(e) {
        const ruler = e.target.closest('#tl-ruler');
        if (ruler) { setTime(trackTime(ruler, e.clientX)); return; }
        const row = e.target.closest('.tl-row');
        if (!row) return;
        const o = canvas.getObjects()[+row.dataset.idx];
        if (!o) return;
        const bar = e.target.closest('.tl-bar');
        const track = row.querySelector('.tl-track');
        if (!bar) {
            if (e.target.closest('.tl-track')) setTime(trackTime(track, e.clientX));
            selectObject(o);
            return;
        }
        e.preventDefault();
        const mode = e.target.classList.contains('tl-handle') ? e.target.dataset.side : 'move';
        const dur = duration(), width = track.getBoundingClientRect().width;
        const start0 = o.inewStart || 0, end0 = o.inewEnd == null ? dur : o.inewEnd, x0 = e.clientX;
        let moved = false;
        const snap = (t) => Math.round(t * 10) / 10;
        const onMove = (ev) => {
            const dt = (ev.clientX - x0) / width * dur;
            if (Math.abs(ev.clientX - x0) > 2) moved = true;
            let s = start0, en = end0;
            if (mode === 'move') { const len = end0 - start0; s = snap(clamp(start0 + dt, 0, dur - len)); en = s + len; }
            else if (mode === 'start') s = snap(clamp(start0 + dt, 0, end0 - 0.2));
            else en = snap(clamp(end0 + dt, start0 + 0.2, dur));
            o.inewStart = s;
            o.inewEnd = en >= dur - 0.05 ? null : en;
            bar.style.left = `${(s / dur) * 100}%`;
            bar.style.width = `${((en - s) / dur) * 100}%`;
            applyTime();
        };
        const onUp = () => {
            window.removeEventListener('pointermove', onMove);
            window.removeEventListener('pointerup', onUp);
            if (moved) changed();
            selectObject(o);
        };
        window.addEventListener('pointermove', onMove);
        window.addEventListener('pointerup', onUp);
    }

    // ------------------------------------------------------------------ pictures, AI pictures, templates panels
    function renderAssets() {
        const tile = (a, i, group) => `<div class="relative group">
            <button type="button" data-${group}="${i}" class="block w-full aspect-square rounded-lg overflow-hidden border border-[#D9D9DE] bg-[#F2F2F7]" title="Đặt lên khung">
                <img src="${esc(a.url)}" alt="" loading="lazy" class="w-full h-full object-cover"></button>
            <button type="button" data-${group}-bg="${i}" class="absolute bottom-1 right-1 px-1.5 py-0.5 rounded bg-black/70 text-white text-[10px] font-semibold">Nền</button>
            ${a.kind === 'ai' ? '<span class="absolute top-1 left-1 px-1 rounded bg-violet-600 text-white text-[9px] font-bold">AI</span>' : ''}</div>`;
        $('post-photos').innerHTML = CFG.post_photos.length
            ? CFG.post_photos.map((p, i) => tile({ ...p, kind: 'post' }, i, 'photo')).join('')
            : '<p class="col-span-3 text-[11px] text-[#8A8A8E]">Bài này không có ảnh.</p>';
        $('asset-grid').innerHTML = S.assets.length
            ? S.assets.map((a, i) => tile(a, i, 'asset')).join('')
            : '<p class="col-span-3 text-[11px] text-[#8A8A8E]">Chưa có ảnh: tải ảnh lên hoặc tạo bằng AI.</p>';
    }

    function onAssetClick(e) {
        const b = e.target.closest('button');
        if (!b) return;
        const d = b.dataset;
        if (d.photo != null) addImageLayer(CFG.post_photos[+d.photo]);
        else if (d.photoBg != null) useAsBackground({ ...CFG.post_photos[+d.photoBg], kind: 'post' });
        else if (d.asset != null) addImageLayer(S.assets[+d.asset], { ai: S.assets[+d.asset].kind === 'ai' });
        else if (d.assetBg != null) useAsBackground(S.assets[+d.assetBg]);
    }

    async function uploadFiles(files) {
        const btn = $('btn-upload');
        btn.disabled = true;
        const added = [];
        try {
            for (const file of files) {
                btn.textContent = `⏳ Đang tải ${added.length + 1}/${files.length}`;
                const fd = new FormData();
                fd.append('post_id', POST_ID);
                fd.append('file', file);
                const data = await api('/api/studio/assets', fd);
                S.assets.unshift(data.asset);
                added.push(data.asset);
            }
        } catch (e) {
            alert(`Không tải được ảnh: ${e.message}`);
        } finally {
            btn.disabled = false;
            btn.textContent = '⬆️ Tải ảnh lên';
            renderAssets();
        }
        if (added.length === 1) await addImageLayer(added[0]);
    }

    function aiAspect() {
        const v = $('ai-aspect').value;
        return v === 'frame' ? S.aspect : v;
    }

    async function aiSuggest() {
        const btn = $('btn-ai-suggest'), box = $('ai-prompt');
        if (box.value.trim() && !confirm('Thay mô tả đang có bằng mô tả AI viết từ bài?')) return;
        btn.disabled = true;
        $('ai-status').textContent = '⏳ AI đang đọc bài và viết mô tả...';
        try {
            const data = await api('/api/studio/ai-image/suggest', { post_id: POST_ID });
            box.value = data.prompt;
            $('ai-status').textContent = 'Đọc lại và sửa mô tả nếu cần, rồi bấm "Tạo ảnh".';
        } catch (e) {
            $('ai-status').textContent = `❌ ${e.message}`;
        } finally {
            btn.disabled = false;
        }
    }

    async function aiImage() {
        const prompt = $('ai-prompt').value.trim();
        if (!prompt) { $('ai-status').textContent = 'Hãy mô tả ảnh cần tạo, hoặc bấm "AI gợi ý mô tả từ bài".'; return; }
        const btn = $('btn-ai-image');
        btn.disabled = true;
        const t0 = Date.now();
        const timer = setInterval(() => { $('ai-status').textContent = `⏳ AI đang vẽ ảnh... ${Math.round((Date.now() - t0) / 1000)} giây`; }, 500);
        try {
            const data = await api('/api/studio/ai-image', { post_id: POST_ID, prompt, aspect: aiAspect() });
            S.assets.unshift(data.asset);
            renderAssets();
            await addImageLayer(data.asset, { ai: true });
            $('ai-status').textContent = `✅ Đã tạo ảnh (${data.model}) và đặt lên khung. Ảnh được lưu ở "Ảnh đã thêm".`;
        } catch (e) {
            $('ai-status').textContent = `❌ ${e.message}`;
        } finally {
            clearInterval(timer);
            btn.disabled = false;
        }
    }

    function renderTemplates() {
        $('builtin-templates').innerHTML = [...Object.entries(THEMES).map(([k, t]) => [k, t.name]), ['clean', '▫️ Gọn · chỉ tiêu đề'], ['empty', '⬜ Trống']]
            .map(([k, name]) => `<button type="button" data-theme="${k}" class="px-2 py-2 rounded-lg border border-[#D9D9DE] bg-white text-left text-[11px] font-semibold hover:bg-[#EFEFF4]">${name}</button>`).join('');
        $('saved-templates').innerHTML = S.templates.length
            ? S.templates.map((t) => `<div class="flex items-center gap-1.5 p-1.5 rounded-lg border border-[#D9D9DE] bg-white">
                <button type="button" data-template="${esc(t.id)}" class="flex-1 min-w-0 text-left"><span class="block truncate text-[11px] font-semibold text-[#1C1C1E]">${esc(t.name)}</span>
                <span class="text-[10px] text-[#8A8A8E]">${esc(t.aspect)}${t.author ? ` · ${esc(t.author)}` : ''}</span></button>
                <button type="button" data-template-delete="${esc(t.id)}" title="Xoá mẫu" class="px-1.5 text-red-500">✕</button></div>`).join('')
            : '<p class="text-[11px] text-[#8A8A8E]">Chưa có mẫu nào. Sắp xếp xong một video đẹp thì bấm "Lưu thành mẫu" để dùng lại cho bài khác.</p>';
    }

    async function onTemplateClick(e) {
        const b = e.target.closest('button');
        if (!b) return;
        const hasLayers = canvas.getObjects().length > 0;
        if (b.dataset.theme) {
            if (hasLayers && !confirm('Thay các lớp đang có bằng mẫu này?')) return;
            canvas.discardActiveObject();
            canvas.remove(...canvas.getObjects());
            if (b.dataset.theme !== 'empty') addLayers(themeObjects(b.dataset.theme), { select: false });
            else changed();
            renderProps();
        } else if (b.dataset.template) {
            if (hasLayers && !confirm('Thay các lớp đang có bằng mẫu này?')) return;
            try {
                const data = await api(`/api/studio/templates/${b.dataset.template}`, undefined, 'GET');
                await loadProject(data.template.design, { fromTemplate: true });
                changed();
            } catch (err) {
                alert(err.message);
            }
        } else if (b.dataset.templateDelete) {
            const t = S.templates.find((x) => x.id === b.dataset.templateDelete);
            if (!confirm(`Xoá mẫu "${t ? t.name : ''}"? Mẫu bị xoá cho cả tòa soạn.`)) return;
            try {
                await api(`/api/studio/templates/${b.dataset.templateDelete}`, undefined, 'DELETE');
                S.templates = S.templates.filter((x) => x.id !== b.dataset.templateDelete);
                renderTemplates();
            } catch (err) {
                alert(err.message);
            }
        }
    }

    async function saveTemplate() {
        const name = prompt('Tên mẫu (ví dụ: Tin nóng dọc – đỏ):');
        if (!name || !name.trim()) return;
        try {
            const data = await api('/api/studio/templates', { name: name.trim(), design: projectData(false) });
            S.templates.push(data.template);
            S.templates.sort((a, b) => a.name.localeCompare(b.name, 'vi'));
            renderTemplates();
            flash($('btn-save-template'), '✓ Đã lưu mẫu');
        } catch (e) {
            alert(`Chưa lưu được mẫu: ${e.message}`);
        }
    }

    // ------------------------------------------------------------------ voiceover
    function fillVoiceSelect() {
        const sel = $('select-voice');
        const items = (window.STUDIO_VOICES || []).filter((v) => v.lang === S.lang);
        sel.innerHTML = items.map((v) => `<option value="${esc(v.key)}">${esc(v.label)}</option>`).join('');
        if (items.some((v) => v.key === window.STUDIO_DEFAULT_VOICE)) sel.value = window.STUDIO_DEFAULT_VOICE;
    }

    function refreshVoiceLabels() {
        $('val-voice-speed').textContent = `${(+$('input-voice-speed').value).toFixed(2)}×`;
        $('val-voice-vol').textContent = `${Math.round($('input-voice-vol').value * 100)}%`;
        $('val-orig-vol').textContent = `${Math.round($('input-orig-vol').value * 100)}%`;
    }

    function voiceChanged() {
        if (S.voice.url) {
            S.voice = { url: '', duration: 0 };
            voiceAudio.removeAttribute('src');
            $('voice-status').textContent = 'Lời bình hoặc giọng đã đổi: bấm tạo lại giọng đọc để nghe đúng.';
        }
        renderTimeline();
        setTime(S.time);
        markDirty();
    }

    function onLanguageChange() {
        const old = labels(), next = $('select-language').value;
        S.lang = next;
        const lb = labels();
        const up = (s) => String(s || '').toUpperCase();
        for (const o of canvas.getObjects()) {
            if (!(o instanceof InewText) || !o.inewRole) continue;
            if (o.inewRole === 'tag' && o.text === old.tag) o.set('text', lb.tag);
            if (o.inewRole === 'footer' && up(o.text) === up(old.footer)) o.set('text', up(lb.footer));
            if (o.inewRole === 'header' && up(o.text) === up(old.header)) o.set('text', up(lb.header));
            if (o.inewRole === 'source' && up(o.text).startsWith(`${up(old.source)}:`)) o.set('text', up(lb.source) + o.text.slice(old.source.length));
            o.initDimensions();
        }
        fillVoiceSelect();
        voiceChanged();
        changed();
    }

    async function aiWriteScript() {
        const voice = $('input-voiceover-text');
        if (voice.value.trim() && !confirm('Thay tiêu đề và lời bình hiện tại bằng bản AI viết?')) return;
        const btn = $('btn-ai-script');
        btn.disabled = true;
        btn.textContent = '⏳ AI đang viết...';
        try {
            const data = await api('/api/video-editor/script', { post_id: POST_ID, language: S.lang });
            voice.value = data.script.voiceover || '';
            const title = data.script.hook_title || '';
            if (title) {
                CFG.texts.headline = title;
                const heads = canvas.getObjects().filter((o) => o.inewRole === 'headline');
                heads.forEach((o) => { o.set('text', title); o.initDimensions(); });
                if (!heads.length) addLayers(TEXT_PRESETS.title(), { select: false });
            }
            voiceChanged();
            changed();
        } catch (e) {
            alert(e.message);
        } finally {
            btn.disabled = false;
            btn.textContent = '✨ AI viết lời';
        }
    }

    async function makeVoicePreview() {
        const btn = $('btn-voice-preview');
        btn.disabled = true;
        $('voice-status').textContent = '⏳ Đang tạo giọng đọc...';
        try {
            const v = voiceSettings();
            const data = await api('/api/video-editor/voiceover', {
                post_id: POST_ID, language: S.lang, voice_key: v.voice_key, voiceover_text: v.text.trim(), voice_speed: v.speed,
            });
            S.voice = { url: `${mediaUrl(data.audio_path)}&t=${Date.now()}`, duration: +data.duration || 0 };
            voiceAudio.src = S.voice.url;
            $('voice-status').textContent = `✅ Giọng đọc dài ${S.voice.duration.toFixed(1)} giây. Bấm ▶ Phát để nghe cùng hình.`;
            renderTimeline();
            setTime(0);
        } catch (e) {
            $('voice-status').textContent = `❌ ${e.message}`;
        } finally {
            btn.disabled = false;
        }
    }

    // ------------------------------------------------------------------ export and render
    async function exportLayers() {
        const out = [];
        const el = document.createElement('canvas');
        const sc = new fabric.StaticCanvas(el, { width: S.W, height: S.H, enableRetinaScaling: false, renderOnAddRemove: false });
        try {
            for (const o of canvas.getObjects()) {
                const c = await o.clone();
                c.set({ visible: true });
                if (c instanceof InewText) c.initDimensions();
                sc.add(c);
                c.setCoords();
                const b = c.getBoundingRect();
                const sh = c.shadow ? (c.shadow.blur || 0) + Math.max(Math.abs(c.shadow.offsetX || 0), Math.abs(c.shadow.offsetY || 0)) : 0;
                const scale = Math.max(Math.abs(c.scaleX), Math.abs(c.scaleY));
                const m = Math.ceil(((c.inewBoxPad || 0) + (c.strokeWidth || 0) + sh) * scale * 1.5 + 6);
                const x0 = Math.max(0, Math.floor(b.left - m)), y0 = Math.max(0, Math.floor(b.top - m));
                const x1 = Math.min(S.W, Math.ceil(b.left + b.width + m)), y1 = Math.min(S.H, Math.ceil(b.top + b.height + m));
                if (x1 - x0 >= 1 && y1 - y0 >= 1) {
                    sc.renderAll();
                    const png = sc.toDataURL({ format: 'png', left: x0, top: y0, width: x1 - x0, height: y1 - y0, multiplier: 1 });
                    out.push({ png, x: x0, y: y0, start: +o.inewStart || 0, end: o.inewEnd == null ? null : +o.inewEnd });
                }
                sc.remove(c);
            }
        } finally {
            sc.dispose();
        }
        return out;
    }

    function roleValue(role) {
        const o = canvas.getObjects().find((x) => x.inewRole === role && x instanceof InewText);
        return o ? o.text : '';
    }

    function showRenderError(msg) {
        const box = $('render-error');
        box.textContent = msg ? `❌ ${msg}` : '';
        box.classList.toggle('hidden', !msg);
    }

    async function renderVideo() {
        if (S.playing) pause();
        canvas.discardActiveObject();
        canvas.requestRenderAll();
        renderProps();
        const btn = $('btn-render');
        btn.disabled = true;
        showRenderError('');
        $('render-result').classList.add('hidden');
        const status = $('render-status'), text = $('render-status-text');
        status.classList.remove('hidden');
        text.textContent = 'Đang chuẩn bị các lớp chữ và ảnh...';
        const t0 = Date.now();
        let timer;
        try {
            const layers = await exportLayers();
            timer = setInterval(() => {
                text.textContent = `Đang tạo giọng đọc và dựng video... ${Math.round((Date.now() - t0) / 1000)} giây (video dài thì lâu hơn)`;
            }, 500);
            const v = voiceSettings();
            const data = await api('/api/video-editor/render', {
                post_id: POST_ID, aspect_ratio: S.aspect,
                start_time: S.trimStart || 0, end_time: S.trimEnd > S.trimStart ? S.trimEnd : null,
                header_text: roleValue('header'), headline_text: roleValue('headline') || CFG.texts.headline,
                source_text: CFG.texts.source, footer_text: roleValue('footer'), language: S.lang,
                voice_key: v.voice_key, voiceover_text: v.text.trim(), voice_speed: v.speed,
                voice_volume: Number.isFinite(v.voice_volume) ? v.voice_volume : 1,
                original_volume: Number.isFinite(v.original_volume) ? v.original_volume : 0.15,
                layers, framing: { fit: S.bg.fit, fill: S.bg.fill, color: S.bg.color, scale: S.bg.scale, dx: Math.round(S.bg.dx), dy: Math.round(S.bg.dy) },
                background: S.bg.source, background_asset: S.bg.asset ? S.bg.asset.rel_path : '',
                project: projectData(),
            });
            S.dirty = false;
            S.lastVideo = data.file_path;
            showResult(data.download_url, data.duration);
        } catch (e) {
            showRenderError(e.message);
        } finally {
            clearInterval(timer);
            status.classList.add('hidden');
            btn.disabled = false;
        }
    }

    function showResult(url, dur) {
        const box = $('render-result');
        const vid = $('render-result-video');
        vid.src = url;
        $('render-result-download').href = `${url}&download=1`;
        $('render-result-duration').textContent = dur ? `(${(+dur).toFixed(1)} giây)` : '';
        box.classList.remove('hidden');
        box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    // ------------------------------------------------------------------ talking MC (lip-sync)
    const MC = { mode: 'talking_photo', layout: 'pip_bottom_right', avatarPath: (window.STUDIO_FIRST_AVATAR || {}).path || '', anchorPath: '' };

    function setLipsyncMode(mode) {
        MC.mode = mode;
        const on = 'py-1.5 rounded-lg font-bold bg-indigo-600 text-white shadow', off = 'py-1.5 rounded-lg font-bold text-[#8A8A8E]';
        $('btn-mode-photo').className = mode === 'talking_photo' ? on : off;
        $('btn-mode-video').className = mode === 'talking_photo' ? off : on;
        $('panel-talking-photo').classList.toggle('hidden', mode !== 'talking_photo');
        $('panel-video-lipsync').classList.toggle('hidden', mode === 'talking_photo');
        $('btn-lipsync-label').textContent = mode === 'talking_photo' ? 'Tạo cử động khẩu hình MC' : 'Khớp lại khẩu hình cho video';
    }

    function mcStatus(msg) {
        const el = $('lipsync-status');
        el.textContent = msg;
        el.classList.toggle('hidden', !msg);
    }

    async function uploadAvatar(file) {
        const fd = new FormData();
        fd.append('file', file);
        mcStatus('Đang tải ảnh MC lên...');
        try {
            const res = await fetch('/api/lipsync/avatars/upload', { method: 'POST', body: fd });
            const data = await res.json();
            if (!data.success) throw new Error(data.detail || 'Không tải được ảnh.');
            MC.avatarPath = data.rel_path;
            document.querySelectorAll('.avatar-card').forEach((c) => c.classList.remove('ring-2', 'ring-indigo-500', 'bg-indigo-50', 'border-indigo-500'));
            mcStatus('✅ Đã tải ảnh MC.');
        } catch (e) {
            mcStatus(`❌ ${e.message}`);
        }
    }

    async function startLipsync() {
        const source = MC.mode === 'talking_photo' ? MC.avatarPath : S.lastVideo;
        $('anchor-result-card').classList.add('hidden');
        if (!source) {
            mcStatus(MC.mode === 'talking_photo' ? '❌ Chưa chọn ảnh MC.' : '❌ Bài này chưa có video: bấm 🎬 Xuất video trước.');
            return;
        }
        const btn = $('btn-gen-lipsync');
        btn.disabled = true;
        try {
            mcStatus('🎙️ Đang tạo giọng đọc cho MC...');
            const v = voiceSettings();
            const voice = await api('/api/video-editor/voiceover', {
                post_id: POST_ID, language: S.lang, voice_key: v.voice_key, voiceover_text: v.text.trim(), voice_speed: v.speed,
            });
            mcStatus('Đang khớp cử động môi theo giọng đọc...');
            const job = await api('/api/lipsync/render', {
                raw_post_id: POST_ID, mode: MC.mode, source_media_path: source, audio_path: voice.audio_path,
                layout: MC.layout, engine: 'local',
            });
            const poll = setInterval(async () => {
                try {
                    const res = await fetch(`/api/lipsync/jobs/${job.job_id}`);
                    if (!res.ok) return;
                    const st = await res.json();
                    if (st.status === 'done') {
                        clearInterval(poll);
                        btn.disabled = false;
                        mcStatus('');
                        MC.anchorPath = st.output_path;
                        $('anchor-duration-text').textContent = `${(st.duration_seconds || 0).toFixed(1)}s`;
                        $('anchor-preview-video').src = st.video_url;
                        $('anchor-result-card').classList.remove('hidden');
                    } else if (st.status === 'failed') {
                        clearInterval(poll);
                        btn.disabled = false;
                        mcStatus(`❌ ${st.error || 'Không tạo được khẩu hình.'}`);
                    }
                } catch (e) { /* keep polling */ }
            }, 1500);
        } catch (e) {
            mcStatus(`❌ ${e.message}`);
            btn.disabled = false;
        }
    }

    async function compositeAnchor() {
        if (!MC.anchorPath) return;
        if (!S.lastVideo) { alert('Chưa có video để lồng MC: bấm 🎬 Xuất video trước.'); return; }
        const btn = $('btn-composite-anchor');
        btn.disabled = true;
        btn.textContent = '⏳ Đang lồng MC...';
        try {
            const data = await api('/api/lipsync/composite', {
                news_video_path: S.lastVideo, anchor_video_path: MC.anchorPath, layout: MC.layout,
                aspect_ratio: S.aspect, raw_post_id: POST_ID,
            });
            S.lastVideo = data.output_path;
            showResult(data.video_url, data.duration_seconds);
            btn.textContent = '✓ Đã lồng MC';
        } catch (e) {
            alert(`Lỗi lồng MC: ${e.message}`);
            btn.textContent = '➕ Lồng MC vào video vừa xuất';
        } finally {
            btn.disabled = false;
        }
    }

    // ------------------------------------------------------------------ UI wiring
    function selectTab(name) {
        document.querySelectorAll('.studio-tab').forEach((t) => t.setAttribute('aria-selected', String(t.dataset.tab === name)));
        document.querySelectorAll('[data-panel]').forEach((p) => { p.hidden = p.dataset.panel !== name; });
    }

    function bindUi() {
        document.querySelectorAll('.studio-tab').forEach((t) => t.addEventListener('click', () => selectTab(t.dataset.tab)));
        $('btn-undo').addEventListener('click', undo);
        $('btn-redo').addEventListener('click', redo);
        $('btn-save-draft').addEventListener('click', saveDraft);
        $('btn-render').addEventListener('click', renderVideo);
        $('btn-play').addEventListener('click', play);

        // frame
        document.querySelectorAll('[data-aspect]').forEach((b) => b.addEventListener('click', () => {
            if (b.dataset.aspect !== S.aspect) setAspect(b.dataset.aspect);
        }));
        document.querySelectorAll('[data-bg-source]').forEach((b) => b.addEventListener('click', () => {
            if (b.disabled) return;
            S.bg.source = b.dataset.bgSource;
            refreshBackground();
            changed();
        }));
        document.querySelectorAll('[data-fit]').forEach((b) => b.addEventListener('click', () => {
            S.bg.fit = b.dataset.fit;
            S.bg.fill = b.dataset.fill;
            refreshBackground();
            changed();
        }));
        $('bg-color').addEventListener('input', (e) => { S.bg.color = e.target.value; $('bg-backdrop').style.background = S.bg.color; });
        $('bg-color').addEventListener('change', changed);
        $('bg-scale').addEventListener('input', (e) => {
            S.bg.scale = clamp(+e.target.value / 100, 0.2, 3);
            $('bg-scale-value').textContent = `${Math.round(S.bg.scale * 100)}%`;
            layoutBackground();
        });
        $('bg-scale').addEventListener('change', changed);
        $('btn-bg-reset').addEventListener('click', () => { Object.assign(S.bg, { scale: 1, dx: 0, dy: 0 }); refreshBackground(); changed(); });
        $('btn-bg-drag').addEventListener('click', () => {
            S.bgDrag = !S.bgDrag;
            $('btn-bg-drag').setAttribute('aria-pressed', String(S.bgDrag));
            $('bg-drag').classList.toggle('hidden', !S.bgDrag);
            canvas.discardActiveObject();
            canvas.requestRenderAll();
        });
        const drag = $('bg-drag');
        drag.addEventListener('pointerdown', (e) => {
            e.preventDefault();
            const x0 = e.clientX, y0 = e.clientY, dx0 = S.bg.dx, dy0 = S.bg.dy;
            const move = (ev) => { S.bg.dx = dx0 + (ev.clientX - x0) / S.zoom; S.bg.dy = dy0 + (ev.clientY - y0) / S.zoom; layoutBackground(); };
            const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); changed(); };
            window.addEventListener('pointermove', move);
            window.addEventListener('pointerup', up);
        });
        let wheelTimer;
        drag.addEventListener('wheel', (e) => {
            e.preventDefault();
            S.bg.scale = clamp(S.bg.scale * (e.deltaY < 0 ? 1.05 : 1 / 1.05), 0.2, 3);
            refreshFrameControls();
            layoutBackground();
            clearTimeout(wheelTimer);
            wheelTimer = setTimeout(changed, 400);
        }, { passive: false });
        const trimChanged = () => {
            S.trimStart = Math.max(0, parseFloat($('trim-start').value) || 0);
            const end = parseFloat($('trim-end').value);
            S.trimEnd = Number.isFinite(end) && end > S.trimStart ? end : 0;
            changed();
        };
        $('trim-start').addEventListener('change', trimChanged);
        $('trim-end').addEventListener('change', trimChanged);
        $('btn-trim-start-now').addEventListener('click', () => { $('trim-start').value = (bgVideo.currentTime || 0).toFixed(1); trimChanged(); });
        $('btn-trim-end-now').addEventListener('click', () => { $('trim-end').value = (bgVideo.currentTime || 0).toFixed(1); trimChanged(); });
        bgVideo.addEventListener('loadedmetadata', () => { layoutBackground(); seekMedia(); });
        bgImg.addEventListener('load', layoutBackground);

        // text, shapes
        document.querySelectorAll('[data-add-text]').forEach((b) => b.addEventListener('click', () => addLayers(TEXT_PRESETS[b.dataset.addText]())));
        document.querySelectorAll('[data-add-shape]').forEach((b) => b.addEventListener('click', () => addLayers([SHAPE_PRESETS[b.dataset.addShape]()])));

        // pictures
        $('post-photos').addEventListener('click', onAssetClick);
        $('asset-grid').addEventListener('click', onAssetClick);
        $('btn-upload').addEventListener('click', () => $('upload-input').click());
        $('upload-input').addEventListener('change', (e) => { const files = [...e.target.files]; e.target.value = ''; if (files.length) uploadFiles(files); });
        $('btn-ai-suggest').addEventListener('click', aiSuggest);
        $('btn-ai-image').addEventListener('click', aiImage);

        // templates
        $('builtin-templates').addEventListener('click', onTemplateClick);
        $('saved-templates').addEventListener('click', onTemplateClick);
        $('btn-save-template').addEventListener('click', saveTemplate);

        // voiceover
        $('select-language').addEventListener('change', onLanguageChange);
        $('btn-ai-script').addEventListener('click', aiWriteScript);
        $('btn-voice-preview').addEventListener('click', makeVoicePreview);
        ['input-voice-speed', 'input-voice-vol', 'input-orig-vol'].forEach((id) => $(id).addEventListener('input', refreshVoiceLabels));
        $('input-voiceover-text').addEventListener('input', voiceChanged);
        $('select-voice').addEventListener('change', voiceChanged);
        $('input-voice-speed').addEventListener('change', voiceChanged);

        // talking MC
        $('btn-mode-photo').addEventListener('click', () => setLipsyncMode('talking_photo'));
        $('btn-mode-video').addEventListener('click', () => setLipsyncMode('video_lipsync'));
        document.querySelectorAll('.avatar-card').forEach((card) => card.addEventListener('click', () => {
            MC.avatarPath = card.dataset.avatarPath;
            document.querySelectorAll('.avatar-card').forEach((c) => c.classList.remove('ring-2', 'ring-indigo-500', 'bg-indigo-50', 'border-indigo-500'));
            card.classList.add('ring-2', 'ring-indigo-500', 'bg-indigo-50', 'border-indigo-500');
        }));
        $('btn-upload-avatar').addEventListener('click', () => $('upload-avatar-file').click());
        $('upload-avatar-file').addEventListener('change', (e) => { if (e.target.files[0]) uploadAvatar(e.target.files[0]); });
        document.querySelectorAll('.anchor-layout').forEach((b) => b.addEventListener('click', () => {
            MC.layout = b.dataset.anchorLayout;
            document.querySelectorAll('.anchor-layout').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
        }));
        $('btn-gen-lipsync').addEventListener('click', startLipsync);
        $('btn-composite-anchor').addEventListener('click', compositeAnchor);

        // properties, timeline
        const props = $('props-body');
        props.addEventListener('input', onPropsInput);
        props.addEventListener('change', onPropsChange);
        props.addEventListener('click', onPropsClick);
        $('timeline').addEventListener('pointerdown', onTimelineDown);

        document.addEventListener('keydown', onKey);
        window.addEventListener('beforeunload', (e) => { if (S.dirty) { e.preventDefault(); e.returnValue = ''; } });
        new ResizeObserver(() => fitStage()).observe(stageWrap);
    }

    function onKey(e) {
        const tag = (e.target.tagName || '').toLowerCase();
        if (['input', 'textarea', 'select'].includes(tag) || e.target.isContentEditable) return;
        const o = canvas.getActiveObject();
        if (o && o.isEditing) return;
        const k = e.key.toLowerCase(), mod = e.ctrlKey || e.metaKey;
        if (mod && k === 'z') { e.preventDefault(); if (e.shiftKey) redo(); else undo(); }
        else if (mod && k === 'y') { e.preventDefault(); redo(); }
        else if (mod && k === 'd') { e.preventDefault(); duplicateSelected(); }
        else if (k === 'delete' || k === 'backspace') { if (o) { e.preventDefault(); removeSelected(); } }
        else if (k === ' ') { e.preventDefault(); play(); }
        else if (o && k.startsWith('arrow')) {
            e.preventDefault();
            const step = e.shiftKey ? 20 : 2;
            canvas.getActiveObjects().forEach((x) => {
                if (k === 'arrowleft') x.left -= step;
                if (k === 'arrowright') x.left += step;
                if (k === 'arrowup') x.top -= step;
                if (k === 'arrowdown') x.top += step;
                x.setCoords();
            });
            canvas.requestRenderAll();
            clearTimeout(onKey.timer);
            onKey.timer = setTimeout(() => { changed(); renderProps(); }, 300);
        }
    }

    function bindCanvas() {
        const selectionChanged = () => { applyTime(); renderProps(); renderTimeline(); };
        canvas.on('selection:created', selectionChanged);
        canvas.on('selection:updated', selectionChanged);
        canvas.on('selection:cleared', selectionChanged);
        canvas.on('object:modified', (e) => {
            (e.target && e.target.getObjects ? e.target.getObjects() : [e.target]).forEach((o) => o && bakeTextScale(o));
            changed();
            renderProps();
        });
        canvas.on('text:changed', (e) => {
            const area = document.querySelector('#props-body [data-prop="text"]');
            if (area && canvas.getActiveObject() === e.target) area.value = e.target.text;
            markDirty();
        });
        canvas.on('text:editing:exited', changed);
    }

    // ------------------------------------------------------------------ start
    async function init() {
        canvas = new fabric.Canvas('studio-canvas', {
            preserveObjectStacking: true, selectionColor: 'rgba(0,122,255,0.08)', selectionBorderColor: '#007AFF',
            selectionLineWidth: 1, stopContextMenu: true, enableRetinaScaling: true,
        });
        bindUi();
        bindCanvas();
        refreshVoiceLabels();
        await loadFonts();
        setAspect('9:16', { remap: false, record: false });
        if (CFG.project && Array.isArray(CFG.project.objects)) {
            await loadProject(CFG.project);
        } else {
            addLayers(themeObjects('red'), { select: false });
        }
        refreshBackground();
        renderAssets();
        renderTemplates();
        S.history = [snapshot()];
        S.future = [];
        S.dirty = false;
        updateUndoButtons();
        renderTimeline();
        setTime(0);
        selectTab('text');
        $('stage-loading').remove();
    }

    // For support and automated checks: the canvas and the editor state
    window.inewStudio = { get canvas() { return canvas; }, state: S, exportLayers, projectData };

    init().catch((e) => {
        console.error(e);
        $('stage-loading').textContent = `Không mở được Video Studio: ${e.message}. Hãy tải lại trang.`;
    });
})();
