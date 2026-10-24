// Flip 7 : calcul en direct du score de manche et confirmation avant envoi.
// Doit rester aligné avec games/flip7/scoring.py (round_score).
document.addEventListener('DOMContentLoaded', function () {
  var form = document.querySelector('.f7-round-form');
  if (!form) return;

  var bonusFlip7 = parseInt(form.dataset.flip7Bonus, 10);
  var target = parseInt(form.dataset.target, 10);

  function toInt(input) {
    var v = parseInt(input.value, 10);
    return isNaN(v) ? 0 : v;
  }

  function entryScore(entry) {
    if (entry.querySelector('.f7-bust').checked) return 0;
    var numbers = toInt(entry.querySelector('.f7-numbers'));
    var bonus = toInt(entry.querySelector('.f7-bonus'));
    var x2 = entry.querySelector('.f7-x2').checked;
    var flip7 = entry.querySelector('.f7-flip7').checked;
    return numbers * (x2 ? 2 : 1) + bonus + (flip7 ? bonusFlip7 : 0);
  }

  function refresh(entry) {
    var bust = entry.querySelector('.f7-bust').checked;
    // Un doublon annule la manche : on grise tout le reste
    entry.querySelectorAll('.f7-numbers, .f7-bonus, .f7-x2, .f7-flip7, .f7-stop').forEach(function (el) {
      el.disabled = bust;
    });
    entry.classList.toggle('is-bust', bust);
    entry.querySelectorAll('.f7-toggle').forEach(function (label) {
      var box = label.querySelector('input');
      label.classList.toggle('checked', box.checked && !box.disabled);
    });
    entry.querySelector('.f7-total').textContent = entryScore(entry);
  }

  form.querySelectorAll('.f7-entry').forEach(function (entry) {
    entry.addEventListener('input', function () { refresh(entry); });
    entry.addEventListener('change', function (e) {
      // Doublon, Flip 7 et Stop s'excluent : une manche se termine d'une seule façon
      if (e.target.classList.contains('f7-ending') && e.target.checked) {
        entry.querySelectorAll('.f7-ending').forEach(function (box) {
          if (box !== e.target) box.checked = false;
        });
      }
      refresh(entry);
    });
    refresh(entry);
  });

  form.addEventListener('submit', function (e) {
    var invalid = Array.from(form.querySelectorAll('.f7-numbers, .f7-bonus')).some(function (input) {
      return !input.disabled && input.value.trim() !== '' && !/^\d+$/.test(input.value.trim());
    });
    if (invalid) {
      e.preventDefault();
      alert('Les chiffres et les bonus doivent être des nombres entiers positifs.');
      return;
    }

    var message = form.dataset.confirmTitle + '\n\n';
    var reachesTarget = false;
    form.querySelectorAll('.f7-entry').forEach(function (entry) {
      var current = parseInt(entry.dataset.current, 10) || 0;
      var score = entryScore(entry);
      var bust = entry.querySelector('.f7-bust').checked;
      if (form.dataset.mode === 'edit') {
        message += entry.dataset.player + ' : ' + (bust ? '💥 0' : score) + ' pts\n';
      } else {
        message += entry.dataset.player + ' : ' + current + ' + ' + (bust ? '💥 0' : score) + ' → ' + (current + score) + ' pts\n';
        if (current + score >= target) reachesTarget = true;
      }
    });
    if (reachesTarget) {
      message += '\n🏁 Au moins un joueur atteint ' + target + ' points : la partie se terminera (sauf égalité en tête).';
    }
    if (!confirm(message)) e.preventDefault();
  });
});
