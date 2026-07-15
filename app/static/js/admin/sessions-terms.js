/* ==========================================================================
   sessions-terms.js — Sessions/Terms nested CRUD, wired to the real API.
   ========================================================================== */

$(function () {
  let sessions = [];

  const $groups = $("#sessionsGroups");

  function render() {
    $groups.empty();

    if (sessions.length === 0) {
      $groups.append('<p class="text-muted">No sessions yet. Add one to get started.</p>');
      return;
    }

    sessions.forEach(function (session) {
      const sessionTerms = session.terms || [];
      const $card = $('<div class="card mb-4"></div>');
      const $header = $('<div class="card-header"></div>');
      $header.append(
        '<h2>' + $('<div>').text(session.name).html() +
        (session.active ? ' <span class="badge badge-success ms-2">Active</span>' : '') +
        '</h2>'
      );
      const $headerActions = $('<div class="d-flex gap-2"></div>');
      if (!session.active) {
        $headerActions.append(
          '<button type="button" class="btn btn-secondary btn-sm js-set-active-session" data-id="' + session.id + '">Set Active</button>'
        );
      }
      $headerActions.append(
        '<button type="button" class="btn btn-primary btn-sm js-add-term" data-session-id="' + session.id + '">' +
        '<i class="bi bi-plus-lg"></i> Add Term</button>'
      );
      $header.append($headerActions);
      $card.append($header);

      const $body = $('<div class="table-wrapper"><table class="data-table"><thead><tr>' +
        '<th>Term</th><th>Status</th><th>Lock</th><th></th></tr></thead><tbody></tbody></table></div>');
      const $tbody = $body.find('tbody');

      if (sessionTerms.length === 0) {
        $tbody.append('<tr><td colspan="4" class="cell-muted">No terms yet for this session.</td></tr>');
      } else {
        sessionTerms.forEach(function (term) {
          const $row = $(
            '<tr data-id="' + term.id + '">' +
              '<td>' + $('<div>').text(term.name).html() + '</td>' +
              '<td>' + (term.active
                ? '<span class="badge badge-success">Active</span>'
                : '<span class="badge badge-neutral">Inactive</span>') + '</td>' +
              '<td>' + (term.locked
                ? '<span class="badge badge-warning"><i class="bi bi-lock-fill"></i> Locked</span>'
                : '<span class="badge badge-info"><i class="bi bi-unlock-fill"></i> Unlocked</span>') + '</td>' +
              '<td class="row-actions">' +
                (!term.active ? '<button type="button" class="btn btn-secondary btn-sm js-set-active-term">Set Active</button>' : '') +
                '<button type="button" class="btn btn-secondary btn-sm js-toggle-lock">' +
                  (term.locked ? 'Unlock' : 'Lock') +
                '</button>' +
              '</td>' +
            '</tr>'
          );
          $tbody.append($row);
        });
      }
      $card.append($body);
      $groups.append($card);
    });
  }

  function loadSessions() {
    window.apiRequest('GET', '/api/sessions').done(function (response) {
      if (response && response.success) {
        sessions = response.sessions;
        render();
      }
    });
  }

  $('#addSessionBtn').on('click', function () {
    $('#sessionName').val('');
    window.openModal($('#sessionModal'));
  });

  $(document).on('click', '.js-add-term', function () {
    $('#termSessionId').val($(this).data('session-id'));
    $('#termName').val('');
    window.openModal($('#termModal'));
  });

  $(document).on('click', '.js-set-active-session', function () {
    const id = Number($(this).data('id'));
    window.apiRequest('PUT', '/api/sessions/' + id + '/activate').done(function (response) {
      if (response && response.success) {
        loadSessions();
        window.showToast('Active session updated.', 'success');
      }
    });
  });

  $(document).on('click', '.js-set-active-term', function () {
    const id = Number($(this).closest('tr').data('id'));
    window.apiRequest('PUT', '/api/terms/' + id + '/activate').done(function (response) {
      if (response && response.success) {
        loadSessions();
        window.showToast('Active term updated.', 'success');
      }
    });
  });

  $(document).on('click', '.js-toggle-lock', function () {
    const $row = $(this).closest('tr');
    const id = Number($row.data('id'));
    const isLocked = $row.find('.badge-warning').length > 0;
    const action = isLocked ? 'unlock' : 'lock';

    window.confirmAction({
      title: (isLocked ? 'Unlock' : 'Lock') + ' this term?',
      body: isLocked
        ? 'Unlocking will allow teachers to edit scores again.'
        : 'Locking will prevent any further score changes for this term.',
      confirmLabel: isLocked ? 'Unlock' : 'Lock',
      danger: !isLocked,
      onConfirm: function () {
        window.apiRequest('PUT', '/api/terms/' + id + '/' + action).done(function (response) {
          if (response && response.success) {
            loadSessions();
            window.showToast('Term ' + action + 'ed.', 'success');
          }
        });
      }
    });
  });

  $('#sessionForm').on('submit', function (e) {
    e.preventDefault();
    const name = $('#sessionName').val().trim();
    if (!name) return;
    const $btn = $('#sessionSaveBtn');
    $btn.prop('disabled', true).find('.btn-spinner').show();

    window.apiRequest('POST', '/api/sessions', { name: name })
      .done(function (response) {
        if (response && response.success) {
          loadSessions();
          window.closeModal($('#sessionModal'));
          window.showToast('Session added.', 'success');
        }
      })
      .always(function () {
        $btn.prop('disabled', false).find('.btn-spinner').hide();
      });
  });

  $('#termForm').on('submit', function (e) {
    e.preventDefault();
    const sessionId = Number($('#termSessionId').val());
    const name = $('#termName').val().trim();
    if (!name) return;
    const $btn = $('#termSaveBtn');
    $btn.prop('disabled', true).find('.btn-spinner').show();

    window.apiRequest('POST', '/api/terms', { sessionId: sessionId, name: name })
      .done(function (response) {
        if (response && response.success) {
          loadSessions();
          window.closeModal($('#termModal'));
          window.showToast('Term added.', 'success');
        }
      })
      .always(function () {
        $btn.prop('disabled', false).find('.btn-spinner').hide();
      });
  });

  loadSessions();
});
