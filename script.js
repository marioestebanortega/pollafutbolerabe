console.log('Iniciando fetch a /resultados...');
fetch('https://pollafutbolerabe.onrender.com/resultados')
//fetch('http://127.0.0.1:10000/resultados')
  .then(res => {
    console.log('Respuesta recibida del backend:', res);
    if (!res.ok) {
      return res.json().then(data => {
        throw new Error(data.error || 'Error al obtener los datos');
      });
    }
    return res.json();
  })
  .then(data => {
    console.log('JSON recibido:', data);
    // Equipos y logos
    document.getElementById('league-logo').src = data.equipos.league.logo;
    document.getElementById('home-logo').src = data.equipos.home.logo;
    document.getElementById('away-logo').src = data.equipos.away.logo;
    document.getElementById('home-name').textContent = data.equipos.home.name;
    document.getElementById('away-name').textContent = data.equipos.away.name;
    document.getElementById('match-title').textContent = `${data.equipos.home.name} vs ${data.equipos.away.name}`;

    // Mostrar marcador principal (resultado real)
    document.getElementById('main-score').textContent = data.resultado_real.final_score;

    // Mostrar información del estadio y status
    document.getElementById('estadio-info').textContent = `${data.estadio.nombre}, ${data.estadio.ciudad}`;
    let statusText = data.status.estado;
    if (data.status.tiempo_extra) {
        statusText += ` (${data.status.minutos}+${data.status.tiempo_extra}')`;
    } else {
        statusText += ` (${data.status.minutos}')`;
    }
    document.getElementById('status-info').textContent = statusText;

    // Resultados
    const tbody = document.querySelector('#resultados-table tbody');
    tbody.innerHTML = '';
    data.resultados.forEach(r => {
      let predLogo = '';
      if (r.predictions.winner.toLowerCase() === 'local') {
        predLogo = `<img src="${data.equipos.home.logo}" alt="Local" style="height:32px;">`;
      } else if (r.predictions.winner.toLowerCase() === 'visitante') {
        predLogo = `<img src="${data.equipos.away.logo}" alt="Visitante" style="height:32px;">`;
      } else {
        predLogo = `<span class="fs-3 fw-bold text-primary">E</span>`;
      }
      tbody.innerHTML += `
        <tr>
          <td>${r.posicion}</td>
          <td>${r.name}</td>
          <td>${r.score}</td>
          <td class="text-center">${predLogo}</td>
          <td>${r.predictions.winner}</td>
          <td>${r.predictions.final_score}</td>
          <td>${r.predictions.first_half}</td>
          <td>${r.predictions.second_half}</td>
        </tr>
      `;
    });
  })
  .catch(err => {
    console.error('Error al hacer fetch a /resultados:', err);
    // Mostrar mensaje de error en la página
    document.querySelector('.container').innerHTML = `
      <div class="alert alert-danger text-center mt-5">
        <h4 class="alert-heading">Error</h4>
        <p>${err.message}</p>
        <hr>
        <p class="mb-0">Por favor, intente nuevamente en unos minutos.</p>
      </div>
    `;
  });