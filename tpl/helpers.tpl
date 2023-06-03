{% macro formatDuration( s, r=1 ) %}
    {% set s = s // r * r %}
    {% set d = s // (24 * 60 * 60) %}
    {% set s = s % (24 * 60 * 60) %}
    {% set h = s // (60 * 60) %}
    {% set s = s % (60 * 60) %}
    {% set m = s // 60 %}
    {% set s = s % 60 %}
    {{ "%dd" % d if d > 0 else '' }}
    {{ "%dh" % h if h > 0 else '' }}
    {{ "%dm" % m if m > 0 else '' }}
    {{ "%ds" % s if s > 0 else '' }}
{% endmacro %}

{% macro formatMeters( m ) %}
    {% if m > 1000 %}
        {{ (m / 1000)|round(1) }} km
    {% else %}
        {{ m|int }} m
    {% endif %}
{% endmacro %}

{% macro jsClock( now, start ) %}
<span class="value">{{ formatDuration( start ) }}</span>
<span class="now">{{ now }}</span>
<span class="start">{{ start }}</span>
{% endmacro %}
