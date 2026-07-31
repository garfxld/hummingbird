use gpui::{
    App, AppContext, DivInspectorState, InteractiveElement, IntoElement, ParentElement,
    StatefulInteractiveElement, Styled, actions, div, prelude::FluentBuilder, px, rgb, rgba,
};
use tracing::warn;

actions!(hummingbird, [ToggleInspector]);

pub fn register_inspector(cx: &mut App) {
    cx.on_action(|_: &ToggleInspector, cx| {
        cx.defer(|cx| {
            let Some(window_id) = cx.active_window() else {
                warn!("No active window to toggle inspector on");
                return;
            };
            let _ = cx.update_window(window_id, |_, window, cx| {
                window.toggle_inspector(cx);
            });
        });
    });

    cx.set_inspector_renderer(Box::new(|inspector, window, cx| {
        let picking = inspector.is_picking();
        let states = inspector.render_inspector_states(window, cx);

        div()
            .id("inspector-panel")
            .size_full()
            .bg(rgb(0x1c1c1c))
            .text_color(rgb(0xe0e0e0))
            .text_size(px(12.0))
            .p_2()
            .gap_2()
            .flex()
            .flex_col()
            .overflow_y_scroll()
            .border_l_1()
            .border_color(rgb(0x333333))
            .child(
                div()
                    .font_weight(gpui::FontWeight::BOLD)
                    .child(if picking {
                        "Inspector — click an element"
                    } else {
                        "Inspector"
                    }),
            )
            .when(states.is_empty(), |this| {
                this.child(
                    div()
                        .text_color(rgba(0xffffff88))
                        .child("No element selected."),
                )
            })
            .children(states)
            .into_any_element()
    }));

    cx.register_inspector_element(
        |id: gpui::InspectorElementId, state: &DivInspectorState, _window, _cx| {
            div()
                .flex()
                .flex_col()
                .gap_1()
                .p_2()
                .rounded_md()
                .bg(rgb(0x262626))
                .child(format!("source: {}", id.path.source_location))
                .child(format!("bounds: {:?}", state.bounds))
                .child(format!("content size: {:?}", state.content_size))
                .child(format!("style: {:#?}", state.base_style))
        },
    );
}
