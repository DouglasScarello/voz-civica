"""Testes do estado compartilhado da UI — foco nos controles vindos dos botões."""

from voz_civica.ui.state import SharedUiState


def test_toggle_pause_zera_amplitude_e_troca_estado():
    state = SharedUiState()
    state.update(state="speaking_ai", amplitude=0.8)

    assert state.toggle_pause() is True
    snapshot = state.read()
    assert snapshot.paused is True
    assert snapshot.state == "paused"
    assert snapshot.amplitude == 0.0

    assert state.toggle_pause() is False
    assert state.read().state == "listening"
    assert state.read().paused is False


def test_toggle_mute_nao_mexe_no_estado_visual():
    state = SharedUiState()
    state.update(state="thinking", amplitude=0.0)

    assert state.toggle_mute() is True
    assert state.read().muted is True
    assert state.read().state == "thinking"

    assert state.toggle_mute() is False
    assert state.read().muted is False


def test_stop_e_consumido_pelo_playback():
    state = SharedUiState()
    assert state.should_stop() is False

    state.request_stop()
    assert state.should_stop() is True

    state.clear_stop()
    assert state.should_stop() is False


def test_read_devolve_copia_e_nao_referencia():
    state = SharedUiState()
    snapshot = state.read()

    state.update(state="speaking_ai", amplitude=0.5)

    # o snapshot antigo não muda quando o estado compartilhado muda
    assert snapshot.state == "listening"
    assert snapshot.amplitude == 0.0
    assert state.read().state == "speaking_ai"
